// Add logging for probe updates
package metrics

import (
	"log"
	"sync"
	"time"
)

func LogProbeUpdate(url string, requestsInFlight int64, avgLatency float64, hotCold string) {
	log.Printf("[Metrics] Probe update: %s RIF=%d Latency=%.6f HotCold=%s", url, requestsInFlight, avgLatency, hotCold)
}

type MetricsManager struct {
	inFlight  int
	latencies []requestLatency
	mu        sync.Mutex
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
	defer m.mu.Unlock()

	m.inFlight++
	log.Printf("[MetricsManager] IncInFlight: now %d", m.inFlight)
}

func (m *MetricsManager) DecInFlight() {
	m.mu.Lock()
	defer m.mu.Unlock()

	if m.inFlight > 0 {
		m.inFlight--
		log.Printf("[MetricsManager] DecInFlight: now %d", m.inFlight)
	}
}

func (m *MetricsManager) AddLatency(d time.Duration) {
	m.mu.Lock()
	defer m.mu.Unlock()

	m.latencies = append(m.latencies, requestLatency{timestamp: time.Now(), duration: d})
	log.Printf("[MetricsManager] AddLatency: added %v, total count %d", d, len(m.latencies))
}

func (m *MetricsManager) AvgLatencyLast5Min() time.Duration {
	m.mu.Lock()
	defer m.mu.Unlock()

	now := time.Now()
	var sum time.Duration
	var count int
	cutoff := now.Add(-5 * time.Minute)
	newLatencies := make([]requestLatency, 0, len(m.latencies))

	for _, l := range m.latencies {
		if l.timestamp.After(cutoff) {
			sum += l.duration
			count++
			newLatencies = append(newLatencies, l)
		}
	}

	m.latencies = newLatencies // prune old

	if count == 0 {
		log.Printf("[MetricsManager] AvgLatencyLast5Min: No data in the last 5 minutes")
		return 0 // Return 0 to indicate no data
	}

	average := sum / time.Duration(count)
	log.Printf("[MetricsManager] AvgLatencyLast5Min: Average latency = %v", average)
	return average
}

func (m *MetricsManager) InFlight() int {
	m.mu.Lock()
	defer m.mu.Unlock()

	return m.inFlight
}
