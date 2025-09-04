package probe

import (
	"encoding/json"
	"io"
	"log"
	"net/http"
	"sort"
	"time"

	"github.com/Pranshu258/OpenPrequal/pkg/contracts"
	"gonum.org/v1/gonum/stat"
)

// AddRIF adds a new RIF value to history
func (p *Probe) AddRIF(rif float64) {
	if len(p.recentRIFs) >= p.maxHistory {
		p.recentRIFs = p.recentRIFs[1:]
	}
	p.recentRIFs = append(p.recentRIFs, rif)
}

// MedianRIF returns the median of recent RIFs
func (p *Probe) MedianRIF() float64 {
	n := len(p.recentRIFs)
	if n == 0 {
		return 0
	}
	sorted := make([]float64, n)
	copy(sorted, p.recentRIFs)
	sort.Float64s(sorted) // Sort the data before calling Quantile
	// gonum/stat Quantile with p=0.5 for median
	return stat.Quantile(0.5, stat.Empirical, sorted, nil)
}

// Status returns 'hot' if current RIF > median, else 'cold'
func (p *Probe) Status(currentRIF float64) string {
	median := p.MedianRIF()
	if currentRIF > median {
		return "hot"
	}
	return "cold"
}

// AddLatency adds a new latency value to history
func (p *Probe) AddLatency(latency float64) {
	if len(p.recentLatencies) >= p.maxHistory {
		p.recentLatencies = p.recentLatencies[1:]
	}
	p.recentLatencies = append(p.recentLatencies, latency)
}

// MedianLatency returns the median of recent latencies
func (p *Probe) MedianLatency() float64 {
	n := len(p.recentLatencies)
	if n == 0 {
		return 0
	}
	sorted := make([]float64, n)
	copy(sorted, p.recentLatencies)
	sort.Float64s(sorted)
	return stat.Quantile(0.5, stat.Empirical, sorted, nil)
}

type Probe struct {
	recentRIFs      []float64
	recentLatencies []float64
	maxHistory      int
}

// AverageLatency returns the arithmetic mean of recent latencies
func (p *Probe) AverageLatency() float64 {
	n := len(p.recentLatencies)
	if n == 0 {
		return 0
	}
	sum := 0.0
	for _, v := range p.recentLatencies {
		sum += v
	}
	return sum / float64(n)
}

func NewProbe(historySize int) *Probe {
	return &Probe{
		recentRIFs:      make([]float64, 0, historySize),
		recentLatencies: make([]float64, 0, historySize),
		maxHistory:      historySize,
	}
}

// ProbeBackend sends a request to the backend /metrics endpoint and returns metrics as ProbeResponse.
func ProbeBackend(url string) (*contracts.ProbeResponse, error) {
	client := &http.Client{Timeout: 2 * time.Second}
	resp, err := client.Get(url + "/metrics")
	if err != nil {
		log.Printf("[ProbeBackend] Error fetching metrics from %s: %v", url, err)
		return nil, err
	}
	defer resp.Body.Close()

	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		log.Printf("[ProbeBackend] Error reading response body from %s: %v", url, err)
		return nil, err
	}
	log.Printf("[ProbeBackend] Raw response from %s: %s", url, string(bodyBytes))

	var probeResp contracts.ProbeResponse
	if err := json.Unmarshal(bodyBytes, &probeResp); err != nil {
		log.Printf("[ProbeBackend] Error decoding JSON from %s: %v", url, err)
		return nil, err
	}
	log.Printf("[ProbeBackend] Decoded ProbeResponse from %s: RequestsInFlight=%d, AverageLatencyMs=%.6f", url, probeResp.RequestsInFlight, probeResp.AverageLatencyMs)
	return &probeResp, nil
}
