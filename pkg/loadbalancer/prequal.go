package loadbalancer

import (
	"context"
	"fmt"
	"log"
	"math"
	"math/rand"
	"sort"
	"sync"
	"time"

	"github.com/Pranshu258/OpenPrequal/pkg/metrics"
	"github.com/Pranshu258/OpenPrequal/pkg/probe"
	"github.com/Pranshu258/OpenPrequal/pkg/registry"
)

// Configuration constants for probing and request tracking
const (
	requestWindowSec       = int64(1)              // sliding window in seconds for RPS
	forcedProbeIntervalSec = int64(20)             // min seconds between forced probes per backend
	probeSleepDuration     = 20 * time.Millisecond // sleep between probe scheduling loops
	probeWorkerCount       = 4                     // number of parallel probe workers
	maxRequestBuffer       = 100000                // capacity for ring buffer of request timestamps
	starvationThresholdSec = int64(1)              // consider a backend starved if not picked within this many seconds
)

// PrequalLoadBalancer selects the cold backend with lowest latency, or if all are hot, the one with lowest RIF
// Implements LoadBalancer interface
type PrequalLoadBalancer struct {
	Registry                   registry.BackendRegistry
	stopProbe                  chan struct{}
	probeHistory               map[string]struct{}
	lastProbeTime              map[string]int64
	requestBuffer              []int64 // ring buffer for timestamps
	rpsHead, rpsTail, rpsCount int
	rpsMu                      sync.Mutex // separate lock for request rate buffer
	mu                         sync.Mutex
	wg                         sync.WaitGroup
	// probe subsystem
	probeTaskQueue *ProbeTaskQueue
	probePool      *ProbePool
	probeManager   *ProbeManager
	// caches and small helpers
	latencyCache     map[string]float64
	latencyCacheTime map[string]int64 // ms
	rifMedianCache   map[string]float64
	rifLastCount     map[string]int
	rifLastValue     map[string]float64
	healthyCache     []string
	healthyCacheTime int64 // ms
	// instrumentation for debugging distribution
	pickCounts map[string]int64
	// starvation avoidance: last time a backend was picked (unix seconds)
	lastPickTime map[string]int64
}

func NewPrequalLoadBalancer(reg registry.BackendRegistry) *PrequalLoadBalancer {
	lb := &PrequalLoadBalancer{
		Registry:         reg,
		stopProbe:        make(chan struct{}),
		probeHistory:     make(map[string]struct{}),
		lastProbeTime:    make(map[string]int64),
		requestBuffer:    make([]int64, maxRequestBuffer),
		latencyCache:     make(map[string]float64),
		latencyCacheTime: make(map[string]int64),
		rifMedianCache:   make(map[string]float64),
		rifLastCount:     make(map[string]int),
		rifLastValue:     make(map[string]float64),
		pickCounts:       make(map[string]int64),
		lastPickTime:     make(map[string]int64),
	}
	// initialize probe subsystem
	lb.probeTaskQueue = NewProbeTaskQueue(100)
	lb.probePool = NewProbePool(1000, 100)
	lb.probeManager = NewProbeManager(reg, lb.probeTaskQueue, lb.probePool, 20)
	lb.startProbeScheduler()
	lb.probeManager.Start()
	// start a lightweight logger to report pick distribution every 5s
	go func() {
		ticker := time.NewTicker(5 * time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-lb.stopProbe:
				return
			case <-ticker.C:
				lb.mu.Lock()
				// snapshot counts
				total := int64(0)
				for _, v := range lb.pickCounts {
					total += v
				}
				if total == 0 {
					lb.mu.Unlock()
					continue
				}
				log.Printf("[Prequal][debug] pick distribution (total=%d):", total)
				for url, v := range lb.pickCounts {
					pct := (float64(v) / float64(total)) * 100.0
					log.Printf("[Prequal][debug] %s: %.2f%% (%d)", url, pct, v)
				}
				lb.mu.Unlock()
			}
		}
	}()
	return lb
}

const (
	latencyCacheTimeoutMs = int64(5) // milliseconds
	healthyCacheTimeoutMs = int64(5) // milliseconds
)

// helper: get cached healthy URLs (short timeout)
func (lb *PrequalLoadBalancer) getHealthyCached() []string {
	nowMs := time.Now().UnixNano() / 1e6
	lb.mu.Lock()
	if lb.healthyCache != nil && nowMs-lb.healthyCacheTime <= healthyCacheTimeoutMs {
		hc := lb.healthyCache
		lb.mu.Unlock()
		return hc
	}
	// rebuild
	backends := lb.Registry.ListBackends()
	healthy := lb.filterHealthyURLs(backends)
	lb.healthyCache = healthy
	lb.healthyCacheTime = nowMs
	lb.mu.Unlock()
	return healthy
}

// helper: get latency with tiny cache; consult probePool first, fallback to registry probe avg
func (lb *PrequalLoadBalancer) getLatencyCached(url string) (float64, bool) {
	nowMs := time.Now().UnixNano() / 1e6
	lb.mu.Lock()
	if t, ok := lb.latencyCacheTime[url]; ok {
		if nowMs-t <= latencyCacheTimeoutMs {
			v := lb.latencyCache[url]
			lb.mu.Unlock()
			return v, true
		}
	}
	lb.mu.Unlock()
	// try probePool
	if lb.probePool != nil {
		if v, ok := lb.probePool.GetCurrentLatency(url); ok {
			lb.mu.Lock()
			lb.latencyCache[url] = v
			lb.latencyCacheTime[url] = nowMs
			lb.mu.Unlock()
			return v, true
		}
	}
	// fallback: check registry Probe
	backends := lb.Registry.ListBackends()
	for _, b := range backends {
		if b.URL == url {
			v := b.Probe.AverageLatency()
			lb.mu.Lock()
			lb.latencyCache[url] = v
			lb.latencyCacheTime[url] = nowMs
			lb.mu.Unlock()
			return v, true
		}
	}
	return 0, false
}

// helper: compute median RIF from probePool with caching keyed by (count,last)
func (lb *PrequalLoadBalancer) getMedianRIF(url string) float64 {
	// fetch rifs
	var rifs []float64
	if lb.probePool != nil {
		rifs = lb.probePool.GetRIFs(url)
	}
	// fallback to registry probe recentRIFs if none
	if len(rifs) == 0 {
		backends := lb.Registry.ListBackends()
		for _, b := range backends {
			if b.URL == url {
				return b.Probe.MedianRIF()
			}
		}
		return 0
	}
	cnt := len(rifs)
	last := rifs[cnt-1]
	// check cache
	lb.mu.Lock()
	if c, ok := lb.rifLastCount[url]; ok {
		if c == cnt && lb.rifLastValue[url] == last {
			v := lb.rifMedianCache[url]
			lb.mu.Unlock()
			return v
		}
	}
	lb.mu.Unlock()
	// compute median
	tmp := make([]float64, len(rifs))
	copy(tmp, rifs)
	sort.Float64s(tmp)
	med := 0.0
	n := len(tmp)
	if n == 0 {
		med = 0
	} else if n%2 == 1 {
		med = tmp[n/2]
	} else {
		med = (tmp[n/2-1] + tmp[n/2]) / 2
	}
	// update cache
	lb.mu.Lock()
	lb.rifMedianCache[url] = med
	lb.rifLastCount[url] = cnt
	lb.rifLastValue[url] = last
	lb.mu.Unlock()
	return med
}

// recordRequest logs the current timestamp and removes entries outside the request window
func (lb *PrequalLoadBalancer) recordRequest() {
	now := time.Now().UnixNano() / 1e9
	cutoff := now - requestWindowSec
	lb.rpsMu.Lock()
	defer lb.rpsMu.Unlock()
	// enqueue at tail
	lb.requestBuffer[lb.rpsTail] = now
	lb.rpsTail = (lb.rpsTail + 1) % len(lb.requestBuffer)
	if lb.rpsCount < len(lb.requestBuffer) {
		lb.rpsCount++
	} else {
		// overwrite oldest if full
		lb.rpsHead = (lb.rpsHead + 1) % len(lb.requestBuffer)
	}
	// drop expired entries
	for lb.rpsCount > 0 {
		oldest := lb.requestBuffer[lb.rpsHead]
		if oldest >= cutoff {
			break
		}
		lb.rpsHead = (lb.rpsHead + 1) % len(lb.requestBuffer)
		lb.rpsCount--
	}
}

// selectColdBackend returns a cold backend URL if available
func (lb *PrequalLoadBalancer) selectColdBackend(backends []*registry.BackendInfo) (string, bool) {
	coldIndices := []int{}
	coldLatency := math.MaxFloat64
	// gather latencies first
	latencies := make([]float64, len(backends))
	for i, b := range backends {
		if b.HotCold != "cold" {
			latencies[i] = math.Inf(1)
			continue
		}
		if v, ok := lb.getLatencyCached(b.URL); ok {
			latencies[i] = v
		} else {
			latencies[i] = b.Probe.AverageLatency()
		}
		if latencies[i] < coldLatency {
			coldLatency = latencies[i]
		}
	}
	if coldLatency == math.MaxFloat64 || math.IsInf(coldLatency, 1) {
		return "", false
	}
	// epsilon tie-breaking: consider candidates within eps of best
	eps := 1e-6
	for i, l := range latencies {
		if l <= coldLatency+eps {
			coldIndices = append(coldIndices, i)
		}
	}
	if len(coldIndices) == 0 {
		return "", false
	}
	// Prefer least-recently-picked among cold candidates to avoid starvation
	lb.mu.Lock()
	defer lb.mu.Unlock()
	var chosenIdx int
	oldest := int64(math.MaxInt64)
	for _, i := range coldIndices {
		url := backends[i].URL
		if t, ok := lb.lastPickTime[url]; ok {
			if t < oldest {
				oldest = t
				chosenIdx = i
			}
		} else {
			// never picked before -> choose immediately
			chosenIdx = i
			oldest = 0
			break
		}
	}
	pick := backends[chosenIdx]
	log.Printf("[Prequal] Selected cold backend: %s (RIF-keyed latency=%.6f)", pick.URL, pick.RIFKeyedLatencyMs)
	return pick.URL, true
}

// selectHotBackend returns a hot backend URL if available
func (lb *PrequalLoadBalancer) selectHotBackend(backends []*registry.BackendInfo) (string, bool) {
	// compute current RIFs and pick with epsilon tie-breaking
	minRIF := math.MaxFloat64
	rifs := make([]float64, len(backends))
	for i, b := range backends {
		// prefer median RIF from probePool (cached), fallback to current RequestsInFlight
		med := lb.getMedianRIF(b.URL)
		if med > 0 {
			rifs[i] = med
		} else {
			rifs[i] = float64(b.RequestsInFlight)
		}
		if rifs[i] < minRIF {
			minRIF = rifs[i]
		}
	}
	if minRIF == math.MaxFloat64 || math.IsInf(minRIF, 1) {
		return "", false
	}
	eps := 1e-6
	candidates := []int{}
	for i, v := range rifs {
		if v <= minRIF+eps {
			candidates = append(candidates, i)
		}
	}
	if len(candidates) == 0 {
		return "", false
	}
	// Prefer least-recently-picked among candidates to avoid starvation
	lb.mu.Lock()
	defer lb.mu.Unlock()
	var chosenIdx int
	oldest := int64(math.MaxInt64)
	for _, i := range candidates {
		url := backends[i].URL
		if t, ok := lb.lastPickTime[url]; ok {
			if t < oldest {
				oldest = t
				chosenIdx = i
			}
		} else {
			// never picked before -> choose immediately
			chosenIdx = i
			oldest = 0
			break
		}
	}
	pick := backends[chosenIdx]
	log.Printf("[Prequal] Selected hot backend: %s (RIF=%d)", pick.URL, pick.RequestsInFlight)
	return pick.URL, true
}

func (lb *PrequalLoadBalancer) PickBackend() string {
	// Track request rate
	lb.recordRequest()
	// Fetch available backends
	backends := lb.Registry.ListBackends()
	if len(backends) == 0 {
		log.Println("[Prequal] No backends available.")
		return ""
	}
	// Early starvation avoidance: prefer any healthy backend that has been
	// unpicked for at least starvationThresholdSec seconds.
	nowSec := time.Now().Unix()
	lb.mu.Lock()
	var earlyStarvedIdx = -1
	var earlyOldest = int64(-1)
	for i, b := range backends {
		// only consider healthy backends
		if b.HotCold == "" {
			continue
		}
		if t, ok := lb.lastPickTime[b.URL]; !ok {
			// never picked -> treat as starved and choose immediately
			earlyStarvedIdx = i
			earlyOldest = -1
			break
		} else if nowSec-t >= starvationThresholdSec {
			// choose the one with the oldest pick time
			if earlyOldest == -1 || t < earlyOldest {
				earlyOldest = t
				earlyStarvedIdx = i
			}
		}
	}
	if earlyStarvedIdx >= 0 {
		url := backends[earlyStarvedIdx].URL
		lb.pickCounts[url]++
		lb.lastPickTime[url] = nowSec
		lb.mu.Unlock()
		log.Printf("[Prequal] Early-starvation: returning backend: %s", url)
		return url
	}
	lb.mu.Unlock()
	// Try selecting a cold backend first
	if url, ok := lb.selectColdBackend(backends); ok {
		lb.mu.Lock()
		lb.pickCounts[url]++
		lb.lastPickTime[url] = time.Now().Unix()
		lb.mu.Unlock()
		return url
	}
	// If no cold, pick hot based on lowest in-flight
	if url, ok := lb.selectHotBackend(backends); ok {
		lb.mu.Lock()
		lb.pickCounts[url]++
		lb.lastPickTime[url] = time.Now().Unix()
		lb.mu.Unlock()
		return url
	}

	// Fallback: random selection
	// As a last resort prefer a starved backend (not picked recently)
	now := time.Now().Unix()
	lb.mu.Lock()
	var starvedIdx = -1
	for i, b := range backends {
		if t, ok := lb.lastPickTime[b.URL]; !ok || now-t >= starvationThresholdSec {
			starvedIdx = i
			break
		}
	}
	if starvedIdx >= 0 {
		url := backends[starvedIdx].URL
		lb.pickCounts[url]++
		lb.lastPickTime[url] = now
		lb.mu.Unlock()
		log.Printf("[Prequal] Fallback: returning starved backend: %s", url)
		return url
	}
	// Otherwise random
	idx := rand.Intn(len(backends))
	url := backends[idx].URL
	lb.pickCounts[url]++
	lb.lastPickTime[url] = now
	lb.mu.Unlock()
	log.Printf("[Prequal] Fallback: returning random backend: %s", url)
	return url
}

// filterHealthyURLs returns URLs of healthy backends
func (lb *PrequalLoadBalancer) filterHealthyURLs(backends []*registry.BackendInfo) []string {
	healthy := make([]string, 0, len(backends))
	for _, b := range backends {
		if b.HotCold != "" {
			healthy = append(healthy, b.URL)
		}
	}
	return healthy
}

// scheduleForcedProbes enqueues probes for backends not probed within forcedProbeIntervalSec
func (lb *PrequalLoadBalancer) scheduleForcedProbes(urls []string, now int64) {
	lb.mu.Lock()
	defer lb.mu.Unlock()
	for _, url := range urls {
		if now-lb.lastProbeTime[url] >= forcedProbeIntervalSec {
			lb.lastProbeTime[url] = now
			// enqueue into deduplicated probe task queue
			if err := lb.probeTaskQueue.AddTask(url); err != nil {
				log.Printf("[Prequal] Probe queue full, dropping forced probe for backend: %s", url)
			} else {
				log.Printf("[Prequal] Forced probe scheduled for backend: %s", url)
			}
		}
	}
}

// scheduleProbabilisticProbe enqueues a probe based on RPS and without replacement
func (lb *PrequalLoadBalancer) scheduleProbabilisticProbe(urls []string, now int64) {
	// calculate request rate using ring buffer
	lb.rpsMu.Lock()
	count := lb.rpsCount
	lb.rpsMu.Unlock()
	rps := float64(count)
	if rps < 1e-6 {
		rps = 1e-6
	}
	R := 50.0 / rps
	if R > 1.0 {
		R = 1.0
	}
	// select without replacement under main lock
	lb.mu.Lock()
	defer lb.mu.Unlock()
	available := make([]string, 0, len(urls))
	for _, url := range urls {
		if _, seen := lb.probeHistory[url]; !seen {
			available = append(available, url)
		}
	}
	if len(available) == 0 {
		lb.probeHistory = make(map[string]struct{})
		available = urls
	}
	if len(available) > 0 && rand.Float64() < R {
		idx := rand.Intn(len(available))
		url := available[idx]
		lb.probeHistory[url] = struct{}{}
		lb.lastProbeTime[url] = now
		if err := lb.probeTaskQueue.AddTask(url); err != nil {
			log.Printf("[Prequal] Probe queue full, dropping probabilistic probe for backend: %s", url)
		} else {
			log.Printf("[Prequal] Probabilistic probe scheduled for backend: %s (R=%.3f, RPS=%.6f)", url, R, rps)
		}
	}
}

// --- ProbeTaskQueue: deduplicated queue of probe tasks ---
type ProbeTaskQueue struct {
	mu  sync.Mutex
	set map[string]struct{}
	ch  chan string
	cap int
}

func NewProbeTaskQueue(capacity int) *ProbeTaskQueue {
	return &ProbeTaskQueue{
		set: make(map[string]struct{}),
		ch:  make(chan string, capacity),
		cap: capacity,
	}
}

// AddTask adds a backend URL to the queue if not already present. Returns error if queue is full.
func (q *ProbeTaskQueue) AddTask(url string) error {
	q.mu.Lock()
	if _, exists := q.set[url]; exists {
		q.mu.Unlock()
		return nil
	}
	// optimistically mark as present
	q.set[url] = struct{}{}
	q.mu.Unlock()

	select {
	case q.ch <- url:
		return nil
	default:
		// remove mark if we couldn't enqueue
		q.mu.Lock()
		delete(q.set, url)
		q.mu.Unlock()
		return fmt.Errorf("queue full")
	}
}

// GetTask blocks until a task is available and returns the URL
func (q *ProbeTaskQueue) GetTask() string {
	url := <-q.ch
	q.mu.Lock()
	delete(q.set, url)
	q.mu.Unlock()
	return url
}

// Size returns number of unique tasks queued
func (q *ProbeTaskQueue) Size() int {
	q.mu.Lock()
	defer q.mu.Unlock()
	return len(q.set)
}

// --- ProbePool: stores recent latencies and RIF history per backend ---
type probeEntry struct {
	latencies []float64
	rifs      []float64
	maxHist   int
	mu        sync.Mutex
	last      time.Time
	curLat    float64
}

type ProbePool struct {
	mu       sync.Mutex
	entries  map[string]*probeEntry
	maxBacks int
}

func NewProbePool(maxBackends int, perBackendHistory int) *ProbePool {
	return &ProbePool{entries: make(map[string]*probeEntry), maxBacks: perBackendHistory}
}

func (p *ProbePool) ensureEntry(url string) *probeEntry {
	p.mu.Lock()
	defer p.mu.Unlock()
	e, ok := p.entries[url]
	if !ok {
		if len(p.entries) >= p.maxBacks {
			// remove one arbitrary entry (oldest by map iteration is acceptable)
			for k := range p.entries {
				delete(p.entries, k)
				break
			}
		}
		e = &probeEntry{latencies: make([]float64, 0, 100), rifs: make([]float64, 0, 100), maxHist: 100}
		p.entries[url] = e
	}
	return e
}

func (p *ProbePool) AddProbe(url string, latency float64, rif float64) {
	e := p.ensureEntry(url)
	e.mu.Lock()
	defer e.mu.Unlock()
	if len(e.latencies) >= e.maxHist {
		e.latencies = e.latencies[1:]
	}
	e.latencies = append(e.latencies, latency)
	if len(e.rifs) >= e.maxHist {
		e.rifs = e.rifs[1:]
	}
	e.rifs = append(e.rifs, rif)
	e.last = time.Now()
	// update current latency
	sum := 0.0
	for _, v := range e.latencies {
		sum += v
	}
	if len(e.latencies) > 0 {
		e.curLat = sum / float64(len(e.latencies))
	}
}

func (p *ProbePool) GetCurrentLatency(url string) (float64, bool) {
	p.mu.Lock()
	e, ok := p.entries[url]
	p.mu.Unlock()
	if !ok {
		return 0, false
	}
	e.mu.Lock()
	defer e.mu.Unlock()
	return e.curLat, true
}

func (p *ProbePool) GetRIFs(url string) []float64 {
	p.mu.Lock()
	e, ok := p.entries[url]
	p.mu.Unlock()
	if !ok {
		return nil
	}
	e.mu.Lock()
	defer e.mu.Unlock()
	out := make([]float64, len(e.rifs))
	copy(out, e.rifs)
	return out
}

// --- ProbeManager: consumes ProbeTaskQueue and runs probes with bounded concurrency ---
type ProbeManager struct {
	reg    registry.BackendRegistry
	queue  *ProbeTaskQueue
	pool   *ProbePool
	sem    chan struct{}
	ctx    context.Context
	cancel context.CancelFunc
	wg     sync.WaitGroup
}

func NewProbeManager(reg registry.BackendRegistry, q *ProbeTaskQueue, p *ProbePool, maxConcurrent int) *ProbeManager {
	ctx, cancel := context.WithCancel(context.Background())
	return &ProbeManager{reg: reg, queue: q, pool: p, sem: make(chan struct{}, maxConcurrent), ctx: ctx, cancel: cancel}
}

func (m *ProbeManager) Start() {
	m.wg.Add(1)
	go m.run()
}

func (m *ProbeManager) Stop() {
	m.cancel()
	m.wg.Wait()
}

func (m *ProbeManager) run() {
	defer m.wg.Done()
	for {
		select {
		case <-m.ctx.Done():
			return
		default:
			// blockingly get a task; but use select to allow cancel
			var url string
			select {
			case <-m.ctx.Done():
				return
			case url = <-m.queue.ch:
				// remove mark
				m.queue.mu.Lock()
				delete(m.queue.set, url)
				m.queue.mu.Unlock()
			}

			// acquire semaphore
			m.sem <- struct{}{}
			m.wg.Add(1)
			go func(u string) {
				defer func() { <-m.sem; m.wg.Done() }()
				result, err := probe.ProbeBackend(u)
				if err != nil {
					log.Printf("[ProbeManager] Probe failed for %s: %v", u, err)
					return
				}
				// update probe pool
				m.pool.AddProbe(u, result.RIFKeyedLatencyMs, float64(result.RequestsInFlight))
				// update registry if in-memory using concurrency-safe helper
				if memReg, ok := m.reg.(*registry.InMemoryBackendRegistry); ok {
					memReg.UpdateBackend(u, func(b *registry.BackendInfo) {
						b.RequestsInFlight = result.RequestsInFlight
						b.AverageLatencyMs = result.AverageLatencyMs
						b.RIFKeyedLatencyMs = result.RIFKeyedLatencyMs
						// record recent request-in-flight and latency history
						rif := float64(result.RequestsInFlight)
						b.Probe.AddRIF(rif)
						b.Probe.AddLatency(result.RIFKeyedLatencyMs)
						b.HotCold = b.Probe.Status(rif)
						metrics.LogProbeUpdate(u, b.RequestsInFlight, b.AverageLatencyMs, b.RIFKeyedLatencyMs, b.HotCold)
					})
				}
			}(url)
		}
	}
}

// startProbeScheduler launches scheduler and probe workers
func (lb *PrequalLoadBalancer) startProbeScheduler() {
	// scheduling loop
	lb.wg.Add(1)
	go func() {
		defer lb.wg.Done()
		ticker := time.NewTicker(probeSleepDuration)
		defer ticker.Stop()
		for {
			select {
			case <-lb.stopProbe:
				// stop scheduling; probeManager is stopped separately
				return
			case <-ticker.C:
				healthy := lb.getHealthyCached()
				now := time.Now().UnixNano() / 1e9
				lb.scheduleForcedProbes(healthy, now)
				lb.scheduleProbabilisticProbe(healthy, now)
			}
		}
	}()
}

// Stop gracefully shuts down scheduler and workers
func (lb *PrequalLoadBalancer) Stop() {
	close(lb.stopProbe)
	lb.wg.Wait()
	if lb.probeManager != nil {
		lb.probeManager.Stop()
	}
}
