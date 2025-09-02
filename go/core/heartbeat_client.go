package core

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"openprequal/contracts"
	"time"
)

type HeartbeatClient struct {
	backend  *contracts.Backend
	proxyURL string
	interval time.Duration
	metrics  *MetricsManager
	cancel   context.CancelFunc
	client   *http.Client
}

func NewHeartbeatClient(b *contracts.Backend, proxyURL string, intervalSec int, metrics *MetricsManager) *HeartbeatClient {
	return &HeartbeatClient{backend: b, proxyURL: proxyURL, interval: time.Duration(intervalSec) * time.Second, metrics: metrics, client: &http.Client{Timeout: 5 * time.Second}}
}

// helper to post backend info to proxy register/unregister endpoints
func (h *HeartbeatClient) postToProxy(path string, payload interface{}) error {
	if h.proxyURL == "" {
		return nil
	}
	data, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	resp, err := h.client.Post(h.proxyURL+path, "application/json", bytes.NewReader(data))
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	return nil
}

func (h *HeartbeatClient) Start() {
	ctx, cancel := context.WithCancel(context.Background())
	h.cancel = cancel

	// initial register: retry a few times while proxy may be starting
	if h.backend != nil {
		maxRetries := 5
		for i := 0; i < maxRetries; i++ {
			if err := h.postToProxy("/register", h.backend); err == nil {
				break
			}
			// exponential-ish backoff
			time.Sleep(200 * time.Millisecond * time.Duration(i+1))
		}
	}

	go func() {
		ticker := time.NewTicker(h.interval)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				// update backend info from metrics
				if h.backend != nil {
					h.backend.AvgLatency = h.metrics.GetAvgLatency()
					h.backend.InFlightRequests = float64(h.metrics.GetInFlight())
					// post updated info to proxy
					h.postToProxy("/register", h.backend)
				}
			case <-ctx.Done():
				return
			}
		}
	}()
}

func (h *HeartbeatClient) Stop() {
	if h.cancel != nil {
		h.cancel()
	}
	// best-effort unregister
	if h.backend != nil {
		// copy minimal struct value for unregister
		var b contracts.Backend = *h.backend
		h.postToProxy("/unregister", b)
	}
}
