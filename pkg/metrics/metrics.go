// Add logging for probe updates
package metrics

import (
	"log"
	"sync"
	"time"
)

// rifBinSize defines the size of each RIF bin for grouping latency entries
const rifBinSize = 10

func LogProbeUpdate(url string, requestsInFlight int64, avgLatency float64, rifKeyedLatency float64, hotCold string) {
	log.Printf("[Metrics] Probe update: %s RIF=%d Latency=%.6f RIFKeyedLatency=%.6f HotCold=%s", url, requestsInFlight, avgLatency, rifKeyedLatency, hotCold)
}

type MetricsManager struct {
	inFlight  int
	latencies []requestLatency
	rifBins   map[int][]rifLatencyEntry // bin index -> latency entries
	mu        sync.Mutex
}

type requestLatency struct {
	timestamp time.Time
	duration  time.Duration
}

type rifLatencyEntry struct {
	timestamp time.Time
	duration  time.Duration
}

func NewMetricsManager() *MetricsManager {
	return &MetricsManager{
		latencies: make([]requestLatency, 0, 1000),
		rifBins:   make(map[int][]rifLatencyEntry),
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

func (m *MetricsManager) AddLatencyWithRIF(d time.Duration, rif int) {
	m.mu.Lock()
	defer m.mu.Unlock()

	// Add to general latencies
	m.latencies = append(m.latencies, requestLatency{timestamp: time.Now(), duration: d})

	// Add to RIF bin-specific latencies
	bin := rif / rifBinSize
	entry := rifLatencyEntry{timestamp: time.Now(), duration: d}
	m.rifBins[bin] = append(m.rifBins[bin], entry)
	log.Printf("[MetricsManager] AddLatencyWithRIF: added %v for RIF=%d (bin=%d), total count %d", d, rif, bin, len(m.latencies))
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

// GetAvgLatencyForRIF returns the average latency for a specific RIF value
// If the exact RIF value is not available, it interpolates from neighboring RIF values
func (m *MetricsManager) GetAvgLatencyForRIF(targetRIF int) time.Duration {
	m.mu.Lock()
	defer m.mu.Unlock()

	// Clean up old entries first (older than 5 minutes)
	m.cleanupOldRIFEntries()

	// Compute target bin and check if we have data for this bin
	targetBin := targetRIF / rifBinSize
	if entries, exists := m.rifBins[targetBin]; exists && len(entries) > 0 {
		var sum time.Duration
		for _, entry := range entries {
			sum += entry.duration
		}
		avg := sum / time.Duration(len(entries))
		log.Printf("[MetricsManager] GetAvgLatencyForRIF: Found data in bin=%d for RIF=%d, avg=%v", targetBin, targetRIF, avg)
		return avg
	}

	// No exact match, try interpolation
	return m.interpolateLatencyForRIF(targetRIF)
}

// cleanupOldRIFEntries removes entries older than 5 minutes from all RIF buckets
func (m *MetricsManager) cleanupOldRIFEntries() {
	cutoff := time.Now().Add(-5 * time.Minute)

	for bin, entries := range m.rifBins {
		newEntries := make([]rifLatencyEntry, 0, len(entries))
		for _, entry := range entries {
			if entry.timestamp.After(cutoff) {
				newEntries = append(newEntries, entry)
			}
		}

		if len(newEntries) == 0 {
			delete(m.rifBins, bin)
		} else {
			m.rifBins[bin] = newEntries
		}
	}
}

// interpolateLatencyForRIF finds the closest RIF values and interpolates
func (m *MetricsManager) interpolateLatencyForRIF(targetRIF int) time.Duration {
	if len(m.rifBins) == 0 {
		log.Printf("[MetricsManager] GetAvgLatencyForRIF: No RIF data available for interpolation")
		return 0
	}

	// Find the closest lower and upper RIF values
	var lowerRIF, upperRIF int
	var hasLower, hasUpper bool

	for bin := range m.rifBins {
		if bin <= targetRIF/rifBinSize && (!hasLower || bin > lowerRIF) {
			lowerRIF = bin
			hasLower = true
		}
		if bin >= targetRIF/rifBinSize && (!hasUpper || bin < upperRIF) {
			upperRIF = bin
			hasUpper = true
		}
	}

	// If we only have one side, use that value
	if hasLower && !hasUpper {
		avg := m.calculateAvgForRIF(lowerRIF)
		log.Printf("[MetricsManager] GetAvgLatencyForRIF: Using lower bound RIF=%d for target=%d, avg=%v", lowerRIF, targetRIF, avg)
		return avg
	}
	if hasUpper && !hasLower {
		avg := m.calculateAvgForRIF(upperRIF)
		log.Printf("[MetricsManager] GetAvgLatencyForRIF: Using upper bound RIF=%d for target=%d, avg=%v", upperRIF, targetRIF, avg)
		return avg
	}

	// If we have both bounds and they're the same, return that value
	if hasLower && hasUpper && lowerRIF == upperRIF {
		avg := m.calculateAvgForRIF(lowerRIF)
		log.Printf("[MetricsManager] GetAvgLatencyForRIF: Exact match after bounds search RIF=%d, avg=%v", lowerRIF, avg)
		return avg
	}

	// Interpolate between lower and upper bounds
	if hasLower && hasUpper {
		lowerAvg := m.calculateAvgForRIF(lowerRIF)
		upperAvg := m.calculateAvgForRIF(upperRIF)

		// Linear interpolation
		ratio := float64(targetRIF-lowerRIF) / float64(upperRIF-lowerRIF)
		interpolated := time.Duration(float64(lowerAvg) + ratio*float64(upperAvg-lowerAvg))

		log.Printf("[MetricsManager] GetAvgLatencyForRIF: Interpolated for RIF=%d between RIF=%d(avg=%v) and RIF=%d(avg=%v), result=%v",
			targetRIF, lowerRIF, lowerAvg, upperRIF, upperAvg, interpolated)
		return interpolated
	}

	log.Printf("[MetricsManager] GetAvgLatencyForRIF: No suitable data for interpolation")
	return 0
}

// calculateAvgForRIF calculates average latency for a specific RIF (assumes mutex is already held)
func (m *MetricsManager) calculateAvgForRIF(rif int) time.Duration {
	entries, exists := m.rifBins[rif]
	if !exists || len(entries) == 0 {
		return 0
	}

	var sum time.Duration
	for _, entry := range entries {
		sum += entry.duration
	}
	return sum / time.Duration(len(entries))
}
