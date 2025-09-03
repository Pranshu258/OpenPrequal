package registry

// BackendRegistry defines the interface for backend management
// (listing, adding, removing, etc.)
type BackendRegistry interface {
	ListBackends() []BackendInfo
	RegisterBackend(url string)
	RemoveBackend(url string)
}

type BackendInfo struct {
	URL              string
	RequestsInFlight int64
	AverageLatencyMs float64
}

type InMemoryBackendRegistry struct {
	Backends map[string]*BackendInfo // key: URL
}

func NewInMemoryBackendRegistry(urls []string) *InMemoryBackendRegistry {
	backends := make(map[string]*BackendInfo)
	for _, url := range urls {
		backends[url] = &BackendInfo{URL: url}
	}
	return &InMemoryBackendRegistry{Backends: backends}
}

func (r *InMemoryBackendRegistry) ListBackends() []BackendInfo {
	result := make([]BackendInfo, 0, len(r.Backends))
	for _, b := range r.Backends {
		result = append(result, *b)
	}
	return result
}

func (r *InMemoryBackendRegistry) RegisterBackend(url string) {
	if _, exists := r.Backends[url]; exists {
		return // already registered
	}
	r.Backends[url] = &BackendInfo{URL: url}
}

func (r *InMemoryBackendRegistry) RemoveBackend(url string) {
	delete(r.Backends, url)
}
