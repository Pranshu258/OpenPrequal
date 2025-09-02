package core

import (
	"openprequal/contracts"
	"strconv"
	"sync"
	"time"
)

type BackendRegistry struct {
	mu               sync.Mutex
	backends         map[string]*contracts.Backend
	lastHeartbeat    map[string]time.Time
	heartbeatTimeout time.Duration
}

func NewBackendRegistry(timeoutSeconds int) *BackendRegistry {
	d := time.Duration(timeoutSeconds) * time.Second
	return &BackendRegistry{backends: make(map[string]*contracts.Backend), lastHeartbeat: make(map[string]time.Time), heartbeatTimeout: d}
}
func keyFor(url string, port int) string { return url + ":" + strconv.Itoa(port) }

func (r *BackendRegistry) Register(b *contracts.Backend) map[string]interface{} {
	r.mu.Lock()
	defer r.mu.Unlock()
	k := keyFor(b.URL, 0)
	r.backends[k] = b
	r.lastHeartbeat[k] = time.Now()
	b.Health = true
	return map[string]interface{}{"status": "registered"}
}

func (r *BackendRegistry) Unregister(b *contracts.Backend) map[string]interface{} {
	r.mu.Lock()
	defer r.mu.Unlock()
	delete(r.backends, keyFor(b.URL, 0))
	delete(r.lastHeartbeat, keyFor(b.URL, 0))
	return map[string]interface{}{"status": "unregistered"}
}

func (r *BackendRegistry) ListBackends() []*contracts.Backend {
	r.mu.Lock()
	defer r.mu.Unlock()
	now := time.Now()
	for k, b := range r.backends {
		if ts, ok := r.lastHeartbeat[k]; ok {
			if now.Sub(ts) > r.heartbeatTimeout {
				b.Health = false
			} else {
				b.Health = true
			}
		}
	}
	out := make([]*contracts.Backend, 0, len(r.backends))
	for _, v := range r.backends {
		out = append(out, v)
	}
	return out
}
