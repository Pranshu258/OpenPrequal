package probe

import (
	"encoding/json"
	"net/http"
	"time"

	"github.com/Pranshu258/OpenPrequal/pkg/contracts"
)

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
