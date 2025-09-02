package main

import (
	"sync"
	"time"
)

type MetricsManager struct {
	mu        sync.Mutex
	inFlight  int
	latencies []requestLatency
}

type requestLatency struct {
	timestamp time.Time
	duration  time.Duration
}

func NewMetricsManager() *MetricsManager {
	return &MetricsManager{
		latencies: make([]requestLatency, 0, 1000),
	}
}

func (m *MetricsManager) IncInFlight() {
	m.mu.Lock()
	m.inFlight++
	m.mu.Unlock()
}

func (m *MetricsManager) DecInFlight() {
	m.mu.Lock()
	if m.inFlight > 0 {
		m.inFlight--
	}
	m.mu.Unlock()
}

func (m *MetricsManager) AddLatency(d time.Duration) {
	m.mu.Lock()
	m.latencies = append(m.latencies, requestLatency{timestamp: time.Now(), duration: d})
	m.mu.Unlock()
}

func (m *MetricsManager) AvgLatencyLast5Min() time.Duration {
	m.mu.Lock()
	defer m.mu.Unlock()
	now := time.Now()
	var sum time.Duration
	var count int
	cutoff := now.Add(-5 * time.Minute)
	newLatencies := m.latencies[:0]
	for _, l := range m.latencies {
		if l.timestamp.After(cutoff) {
			sum += l.duration
			count++
			newLatencies = append(newLatencies, l)
		}
	}
	m.latencies = newLatencies // prune old
	if count == 0 {
		return 0
	}
	return sum / time.Duration(count)
}

func (m *MetricsManager) InFlight() int {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.inFlight
}
