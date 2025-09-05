package loadbalancer

import (
	"context"
	"fmt"
	"log"
	"math"
	"math/rand"
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
	rand           *rand.Rand
}

func NewPrequalLoadBalancer(reg registry.BackendRegistry) *PrequalLoadBalancer {
	lb := &PrequalLoadBalancer{
		Registry:      reg,
		stopProbe:     make(chan struct{}),
		probeHistory:  make(map[string]struct{}),
		lastProbeTime: make(map[string]int64),
		requestBuffer: make([]int64, maxRequestBuffer),
		rand:          rand.New(rand.NewSource(time.Now().UnixNano())),
	}
	// initialize probe subsystem
	lb.probeTaskQueue = NewProbeTaskQueue(100)
	lb.probePool = NewProbePool(1000, 100)
	lb.probeManager = NewProbeManager(reg, lb.probeTaskQueue, lb.probePool, 20)
	lb.startProbeScheduler()
	lb.probeManager.Start()
	return lb
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
	for i, b := range backends {
		if b.HotCold != "cold" {
			continue
		}
		latency := b.Probe.AverageLatency()
		if latency < coldLatency {
			coldLatency = latency
			coldIndices = []int{i}
		} else if latency == coldLatency {
			coldIndices = append(coldIndices, i)
		}
	}
	if len(coldIndices) == 0 {
		return "", false
	}
	idx := coldIndices[0]
	if len(coldIndices) > 1 {
		idx = coldIndices[lb.rand.Intn(len(coldIndices))]
	}
	pick := backends[idx]
	log.Printf("[Prequal] Selected cold backend: %s (RIF-keyed latency=%.6f)", pick.URL, pick.RIFKeyedLatencyMs)
	return pick.URL, true
}

// selectHotBackend returns a hot backend URL if available
func (lb *PrequalLoadBalancer) selectHotBackend(backends []*registry.BackendInfo) (string, bool) {
	minRIF := math.MaxFloat64
	minIndices := []int{}
	for i, b := range backends {
		rif := float64(b.RequestsInFlight)
		if rif < minRIF {
			minRIF = rif
			minIndices = []int{i}
		} else if rif == minRIF {
			minIndices = append(minIndices, i)
		}
	}
	if len(minIndices) == 0 {
		return "", false
	}
	idx := minIndices[0]
	if len(minIndices) > 1 {
		idx = minIndices[lb.rand.Intn(len(minIndices))]
	}
	pick := backends[idx]
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

	// Try selecting a cold backend first
	if url, ok := lb.selectColdBackend(backends); ok {
		return url
	}
	// If no cold, pick hot based on lowest in-flight
	if url, ok := lb.selectHotBackend(backends); ok {
		return url
	}

	// Fallback: random selection
	idx := lb.rand.Intn(len(backends))
	log.Printf("[Prequal] Fallback: returning random backend: %s", backends[idx].URL)
	return backends[idx].URL
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
	R := 5.0 / rps
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
	if len(available) > 0 && lb.rand.Float64() < R {
		idx := lb.rand.Intn(len(available))
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
				backends := lb.Registry.ListBackends()
				healthy := lb.filterHealthyURLs(backends)
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
