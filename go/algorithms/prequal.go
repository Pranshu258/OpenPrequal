package algorithms

import (
	"math"
	"math/rand"
	"sort"
	"sync"
	"time"

	"openprequal/abstractions"
	"openprequal/contracts"
	"openprequal/core"
)

// Prequal implements a more complete PrequalLoadBalancer port.
type Prequal struct {
	reg  abstractions.Registry
	pool *core.ProbePool
	tq   *core.ProbeTaskQueue

	mu                     sync.Mutex
	probeHistory           map[string]struct{}
	requestTimestamps      []time.Time
	lastProbeTime          map[string]time.Time
	rifMedianCache         map[string]float64
	rifLastInfoCount       map[string]int
	rifLastInfoLast        map[string]float64
	latencyCache           map[string]float64
	latencyCacheTime       map[string]time.Time
	healthyBackendsCache   []contracts.Backend
	healthyBackendsCacheAt time.Time
	cacheTimeout           time.Duration

	stopCh chan struct{}
}

func NewPrequal(reg abstractions.Registry, pool *core.ProbePool, tq *core.ProbeTaskQueue) *Prequal {
	p := &Prequal{
		reg:              reg,
		pool:             pool,
		tq:               tq,
		probeHistory:     make(map[string]struct{}),
		lastProbeTime:    make(map[string]time.Time),
		rifMedianCache:   make(map[string]float64),
		rifLastInfoCount: make(map[string]int),
		rifLastInfoLast:  make(map[string]float64),
		latencyCache:     make(map[string]float64),
		latencyCacheTime: make(map[string]time.Time),
		cacheTimeout:     5 * time.Millisecond,
		stopCh:           make(chan struct{}),
	}
	go p.probeSchedulerLoop()
	return p
}

func median(xs []float64) float64 {
	if len(xs) == 0 {
		return 0
	}
	sort.Float64s(xs)
	n := len(xs)
	if n%2 == 1 {
		return xs[n/2]
	}
	return (xs[n/2-1] + xs[n/2]) / 2
}

// classifyBackends returns cold, hot lists and rifs map keyed by backend URL.
func (p *Prequal) classifyBackends(backends []contracts.Backend) (cold []contracts.Backend, hot []contracts.Backend, rifsMap map[string][]float64) {
	rifsMap = make(map[string][]float64)
	// fetch RIFs
	for _, b := range backends {
		rifsMap[b.URL] = p.pool.GetRIFValues(b.URL)
	}

	for _, backend := range backends {
		rifs := rifsMap[backend.URL]
		if len(rifs) == 0 {
			cold = append(cold, backend)
			continue
		}
		count := len(rifs)
		last := rifs[count-1]

		// use cached median when possible
		if p.rifLastInfoCount[backend.URL] == count && p.rifLastInfoLast[backend.URL] == last {
			// cached
		} else {
			med := median(append([]float64(nil), rifs...))
			p.rifMedianCache[backend.URL] = med
			p.rifLastInfoCount[backend.URL] = count
			p.rifLastInfoLast[backend.URL] = last
		}

		med := p.rifMedianCache[backend.URL]
		if last < med {
			cold = append(cold, backend)
		} else {
			hot = append(hot, backend)
		}
	}
	return
}

// selectBackend implements cold/hot selection logic.
func (p *Prequal) selectBackend(cold, hot []contracts.Backend, rifsMap map[string][]float64) *contracts.Backend {
	if len(cold) > 0 {
		now := time.Now()
		cachedLat := make([]*float64, len(cold))
		var uncached []contracts.Backend
		for i, b := range cold {
			ct, ok := p.latencyCacheTime[b.URL]
			if ok && now.Sub(ct) < p.cacheTimeout {
				v := p.latencyCache[b.URL]
				cachedLat[i] = &v
			} else {
				cachedLat[i] = nil
				uncached = append(uncached, b)
			}
		}
		// fetch uncached latencies
		for _, b := range uncached {
			if latptr := p.pool.GetCurrentLatency(b.URL); latptr != nil {
				p.latencyCache[b.URL] = *latptr
				p.latencyCacheTime[b.URL] = now
			}
		}
		// pick best with random tie-breaking
		bestLat := math.Inf(1)
		var candidates []int
		for i, b := range cold {
			var lat float64 = math.Inf(1)
			if v := cachedLat[i]; v != nil {
				lat = *v
			} else if v2, ok := p.latencyCache[b.URL]; ok {
				lat = v2
			}
			if lat < bestLat {
				bestLat = lat
				candidates = []int{i}
			} else if lat == bestLat {
				candidates = append(candidates, i)
			}
		}
		if len(candidates) > 0 {
			chosenIdx := candidates[rand.Intn(len(candidates))]
			bb := cold[chosenIdx]
			return &bb
		}
	}

	// hot selection: use rifsMap if provided
	if len(hot) > 0 {
		curRifs := make([]float64, len(hot))
		if rifsMap != nil {
			for i, b := range hot {
				vals := rifsMap[b.URL]
				if len(vals) > 0 {
					curRifs[i] = vals[len(vals)-1]
				} else {
					curRifs[i] = math.Inf(1)
				}
			}
		} else {
			for i, b := range hot {
				vals := p.pool.GetRIFValues(b.URL)
				if len(vals) > 0 {
					curRifs[i] = vals[len(vals)-1]
				} else {
					curRifs[i] = math.Inf(1)
				}
			}
		}
		// find min with random tie-breaking
		bestVal := math.Inf(1)
		var candidates []int
		for i, v := range curRifs {
			if v < bestVal {
				bestVal = v
				candidates = []int{i}
			} else if v == bestVal {
				candidates = append(candidates, i)
			}
		}
		if len(candidates) > 0 {
			chosenIdx := candidates[rand.Intn(len(candidates))]
			bb := hot[chosenIdx]
			return &bb
		}
	}

	return nil
}

// scheduleProbeTasks follows the Python scheduling logic (probabilistic + forced probes).
func (p *Prequal) scheduleProbeTasks(healthyBackends []contracts.Backend) {
	p.mu.Lock()
	now := time.Now()
	// append timestamp and trim window
	p.requestTimestamps = append(p.requestTimestamps, now)
	cutoff := now.Add(-1 * time.Second)
	// pop from front while older than cutoff
	i := 0
	for ; i < len(p.requestTimestamps); i++ {
		if p.requestTimestamps[i].After(cutoff) {
			break
		}
	}
	if i > 0 {
		p.requestTimestamps = p.requestTimestamps[i:]
	}
	rps := float64(len(p.requestTimestamps))
	if rps < 1e-6 {
		rps = 1e-6
	}
	R := 5.0 / rps
	if R > 1.0 {
		R = 1.0
	}

	backendIDs := make(map[string]struct{})
	for _, b := range healthyBackends {
		backendIDs[b.URL] = struct{}{}
	}
	// intersect probeHistory
	for k := range p.probeHistory {
		if _, ok := backendIDs[k]; !ok {
			delete(p.probeHistory, k)
		}
	}

	// forced probes (min interval 20s)
	minProbeInterval := 20 * time.Second
	var forced []string
	for id := range backendIDs {
		if now.Sub(p.lastProbeTime[id]) >= minProbeInterval {
			forced = append(forced, id)
		}
	}
	// collect tasks to schedule while locked, call AddTask after unlocking
	tasksToSchedule := make([]string, 0)
	for _, id := range forced {
		p.lastProbeTime[id] = now
		tasksToSchedule = append(tasksToSchedule, id)
	}

	// probabilistic scheduling
	available := make([]string, 0)
	for id := range backendIDs {
		if _, seen := p.probeHistory[id]; !seen {
			available = append(available, id)
		}
	}
	if len(available) == 0 {
		// reset
		p.probeHistory = make(map[string]struct{})
		for id := range backendIDs {
			available = append(available, id)
		}
	}
	if len(available) > 0 && rand.Float64() < R {
		idx := rand.Intn(len(available))
		id := available[idx]
		p.probeHistory[id] = struct{}{}
		p.lastProbeTime[id] = now
		tasksToSchedule = append(tasksToSchedule, id)
	}
	p.mu.Unlock()

	// schedule tasks after unlocking
	for _, id := range tasksToSchedule {
		go p.tq.AddTask(id)
	}
}

func (p *Prequal) probeSchedulerLoop() {
	ticker := time.NewTicker(20 * time.Millisecond)
	defer ticker.Stop()
	for {
		select {
		case <-ticker.C:
			all := p.reg.ListBackends()
			healthy := make([]contracts.Backend, 0)
			for _, b := range all {
				if b.Health {
					healthy = append(healthy, b)
				}
			}
			if len(healthy) > 0 {
				p.scheduleProbeTasks(healthy)
			}
		case <-p.stopCh:
			return
		}
	}
}

// Next returns the selected backend URL (as Backend pointer) following the Prequal logic.
func (p *Prequal) Next() *contracts.Backend {
	p.mu.Lock()
	now := time.Now()
	if p.healthyBackendsCache == nil || now.Sub(p.healthyBackendsCacheAt) > p.cacheTimeout {
		all := p.reg.ListBackends()
		p.healthyBackendsCache = nil
		for _, b := range all {
			if b.Health {
				p.healthyBackendsCache = append(p.healthyBackendsCache, b)
			}
		}
		p.healthyBackendsCacheAt = now
	}
	healthy := append([]contracts.Backend(nil), p.healthyBackendsCache...)
	p.mu.Unlock()

	if len(healthy) == 0 {
		return nil
	}

	// classification
	p.mu.Lock()
	cold, hot, rifs := p.classifyBackends(healthy)
	p.mu.Unlock()

	selected := p.selectBackend(cold, hot, rifs)
	if selected != nil {
		return selected
	}

	// fallback random
	return &healthy[rand.Intn(len(healthy))]
}

// Stop stops the background scheduler.
func (p *Prequal) Stop() { close(p.stopCh) }
