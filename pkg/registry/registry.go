package registry

import (
	"sort"
	"sync"

	"github.com/Pranshu258/OpenPrequal/pkg/probe"
)

// BackendRegistry defines the interface for backend management
// (listing, adding, removing, etc.)
type BackendRegistry interface {
	ListBackends() []*BackendInfo
	RegisterBackend(url string)
	RemoveBackend(url string)
}

type BackendInfo struct {
	URL               string
	RequestsInFlight  int64
	AverageLatencyMs  float64
	RIFKeyedLatencyMs float64
	HotCold           string // "hot" or "cold"
	Probe             *probe.Probe
}

type InMemoryBackendRegistry struct {
	mu       sync.RWMutex
	Backends map[string]*BackendInfo // key: URL
}

func NewInMemoryBackendRegistry(urls []string) *InMemoryBackendRegistry {
	backends := make(map[string]*BackendInfo)
	for _, url := range urls {
		backends[url] = &BackendInfo{
			URL:     url,
			HotCold: "cold",
			Probe:   probe.NewProbe(100), // history size 10, adjust as needed
		}
	}
	return &InMemoryBackendRegistry{Backends: backends}
}

func (r *InMemoryBackendRegistry) ListBackends() []*BackendInfo {
	r.mu.RLock()
	defer r.mu.RUnlock()
	// deterministic order: sort backend URLs
	keys := make([]string, 0, len(r.Backends))
	for url := range r.Backends {
		keys = append(keys, url)
	}
	sort.Strings(keys)
	result := make([]*BackendInfo, 0, len(keys))
	for _, url := range keys {
		result = append(result, r.Backends[url])
	}
	return result
}

func (r *InMemoryBackendRegistry) RegisterBackend(url string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	if _, exists := r.Backends[url]; exists {
		return // already registered
	}
	r.Backends[url] = &BackendInfo{
		URL:     url,
		HotCold: "cold",
		Probe:   probe.NewProbe(10), // history size 10, adjust as needed
	}
}

func (r *InMemoryBackendRegistry) RemoveBackend(url string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	delete(r.Backends, url)
}
