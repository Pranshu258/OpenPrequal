package core

import (
	"sort"
	"sync"
)

type MetricsManager struct {
	mu           sync.Mutex
	inFlight     int
	rifLatencies map[int][]float64
	rifBins      []int
}

func NewMetricsManager(rifBins []int) *MetricsManager {
	mm := &MetricsManager{rifLatencies: make(map[int][]float64)}
	if len(rifBins) > 0 {
		sort.Ints(rifBins)
		mm.rifBins = rifBins
	}
	return mm
}

func (m *MetricsManager) IncInFlight() { m.mu.Lock(); m.inFlight++; m.mu.Unlock() }
func (m *MetricsManager) DecInFlight() {
	m.mu.Lock()
	if m.inFlight > 0 {
		m.inFlight--
	}
	m.mu.Unlock()
}
func (m *MetricsManager) GetInFlight() int { m.mu.Lock(); v := m.inFlight; m.mu.Unlock(); return v }

func (m *MetricsManager) observeLatency(rif int, latency float64) {
	key := rif
	if len(m.rifBins) > 0 {
		// find first bin >= rif
		i := sort.SearchInts(m.rifBins, rif)
		if i >= len(m.rifBins) {
			key = m.rifBins[len(m.rifBins)-1]
		} else {
			key = m.rifBins[i]
		}
	}
	m.rifLatencies[key] = append(m.rifLatencies[key], latency)
}

func (m *MetricsManager) RecordLatency(latency float64) {
	m.mu.Lock()
	rif := m.inFlight
	m.observeLatency(rif, latency)
	m.mu.Unlock()
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

func (m *MetricsManager) GetAvgLatency() float64 {
	m.mu.Lock()
	rif := m.inFlight
	key := rif
	if len(m.rifBins) > 0 {
		i := sort.SearchInts(m.rifBins, rif)
		if i >= len(m.rifBins) {
			key = m.rifBins[len(m.rifBins)-1]
		} else {
			key = m.rifBins[i]
		}
	}
	samples := m.rifLatencies[key]
	if len(samples) > 0 {
		s := median(samples)
		m.mu.Unlock()
		return s
	}

	// fallback: use any available samples
	for _, k := range m.rifBins {
		if s := m.rifLatencies[k]; len(s) > 0 {
			med := median(s)
			m.mu.Unlock()
			return med
		}
	}
	m.mu.Unlock()
	return 0.0
}
