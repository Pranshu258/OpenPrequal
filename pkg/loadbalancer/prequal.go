package loadbalancer

import (
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
	probeQueue                 chan string
	stopProbe                  chan struct{}
	probeHistory               map[string]struct{}
	lastProbeTime              map[string]int64
	requestBuffer              []int64 // ring buffer for timestamps
	rpsHead, rpsTail, rpsCount int
	rpsMu                      sync.Mutex // separate lock for request rate buffer
	mu                         sync.Mutex
	wg                         sync.WaitGroup
	workersWg                  sync.WaitGroup // wait for probe workers
	rand                       *rand.Rand
}

func NewPrequalLoadBalancer(reg registry.BackendRegistry) *PrequalLoadBalancer {
	lb := &PrequalLoadBalancer{
		Registry:      reg,
		probeQueue:    make(chan string, 100),
		stopProbe:     make(chan struct{}),
		probeHistory:  make(map[string]struct{}),
		lastProbeTime: make(map[string]int64),
		requestBuffer: make([]int64, maxRequestBuffer),
		rand:          rand.New(rand.NewSource(time.Now().UnixNano())),
	}
	lb.startProbeScheduler()
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
		if b.RIFKeyedLatencyMs < coldLatency {
			coldLatency = b.RIFKeyedLatencyMs
			coldIndices = []int{i}
		} else if b.RIFKeyedLatencyMs == coldLatency {
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
			select {
			case lb.probeQueue <- url:
				log.Printf("[Prequal] Forced probe scheduled for backend: %s", url)
			default:
				log.Printf("[Prequal] Probe queue full, dropping forced probe for backend: %s", url)
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
		select {
		case lb.probeQueue <- url:
			log.Printf("[Prequal] Probabilistic probe scheduled for backend: %s (R=%.3f, RPS=%.6f)", url, R, rps)
		default:
			log.Printf("[Prequal] Probe queue full, dropping probabilistic probe for backend: %s", url)
		}
	}
}

// probeWorker processes probeQueue entries concurrently
func (lb *PrequalLoadBalancer) probeWorker() {
	defer lb.workersWg.Done()
	for url := range lb.probeQueue {
		result, err := probe.ProbeBackend(url)
		if err != nil {
			log.Printf("[Prequal] Probe failed for backend: %s, err: %v", url, err)
			continue
		}
		if memReg, ok := lb.Registry.(*registry.InMemoryBackendRegistry); ok {
			if b, exists := memReg.Backends[url]; exists {
				b.RequestsInFlight = result.RequestsInFlight
				b.AverageLatencyMs = result.AverageLatencyMs
				b.RIFKeyedLatencyMs = result.RIFKeyedLatencyMs
				rif := float64(result.RequestsInFlight)
				b.Probe.AddRIF(rif)
				b.HotCold = b.Probe.Status(rif)
				metrics.LogProbeUpdate(url, b.RequestsInFlight, b.AverageLatencyMs, b.RIFKeyedLatencyMs, b.HotCold)
			}
		}
	}
}

// startProbeScheduler launches scheduler and probe workers
func (lb *PrequalLoadBalancer) startProbeScheduler() {
	// spawn probe worker pool
	for i := 0; i < probeWorkerCount; i++ {
		lb.workersWg.Add(1)
		go lb.probeWorker()
	}
	// scheduling loop
	lb.wg.Add(1)
	go func() {
		defer lb.wg.Done()
		ticker := time.NewTicker(probeSleepDuration)
		defer ticker.Stop()
		for {
			select {
			case <-lb.stopProbe:
				// stop scheduling and close queue to signal workers
				close(lb.probeQueue)
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
	lb.workersWg.Wait()
}
