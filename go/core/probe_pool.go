package core

import (
	"sync"
)

type ProbeEntry struct {
	Latencies []float64
	RIFValues []float64
}

type ProbePool struct {
	mu          sync.Mutex
	probes      map[string]*ProbeEntry
	maxBackends int
}

func NewProbePool() *ProbePool {
	return &ProbePool{probes: make(map[string]*ProbeEntry), maxBackends: 16}
}

func (p *ProbePool) AddProbe(backendID string, latency float64, rif float64) {
	p.mu.Lock()
	defer p.mu.Unlock()
	if _, ok := p.probes[backendID]; !ok {
		if len(p.probes) >= p.maxBackends {
			// remove arbitrary oldest entry
			for k := range p.probes {
				delete(p.probes, k)
				break
			}
		}
		p.probes[backendID] = &ProbeEntry{Latencies: make([]float64, 0), RIFValues: make([]float64, 0)}
	}
	e := p.probes[backendID]
	e.Latencies = append(e.Latencies, latency)
	e.RIFValues = append(e.RIFValues, rif)
}

func (p *ProbePool) GetCurrentLatency(backendID string) *float64 {
	p.mu.Lock()
	defer p.mu.Unlock()
	e, ok := p.probes[backendID]
	if !ok || len(e.Latencies) == 0 {
		return nil
	}
	sum := 0.0
	for _, v := range e.Latencies {
		sum += v
	}
	avg := sum / float64(len(e.Latencies))
	return &avg
}

// GetRIFValues returns a copy of RIF values recorded for a backend.
func (p *ProbePool) GetRIFValues(backendID string) []float64 {
	p.mu.Lock()
	defer p.mu.Unlock()
	e, ok := p.probes[backendID]
	if !ok || len(e.RIFValues) == 0 {
		return nil
	}
	out := make([]float64, len(e.RIFValues))
	copy(out, e.RIFValues)
	return out
}
