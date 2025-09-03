package probe

import (
	"encoding/json"
	"net/http"
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

// Median returns the median of recent RIFs
func (p *Probe) Median() float64 {
	n := len(p.recentRIFs)
	if n == 0 {
		return 0
	}
	sorted := make([]float64, n)
	copy(sorted, p.recentRIFs)
	// gonum/stat Quantile with p=0.5 for median
	return stat.Quantile(0.5, stat.Empirical, sorted, nil)
}

// Status returns 'hot' if current RIF > median, else 'cold'
func (p *Probe) Status(currentRIF float64) string {
	median := p.Median()
	if currentRIF > median {
		return "hot"
	}
	return "cold"
}

type Probe struct {
	recentRIFs []float64
	maxHistory int
}

func NewProbe(historySize int) *Probe {
	return &Probe{
		recentRIFs: make([]float64, 0, historySize),
		maxHistory: historySize,
	}
}

// ProbeBackend sends a request to the backend /metrics endpoint and returns metrics as ProbeResponse.
func ProbeBackend(url string) (*contracts.ProbeResponse, error) {
	client := &http.Client{Timeout: 2 * time.Second}
	resp, err := client.Get(url + "/metrics")
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var probeResp contracts.ProbeResponse
	if err := json.NewDecoder(resp.Body).Decode(&probeResp); err != nil {
		return nil, err
	}
	return &probeResp, nil
}
