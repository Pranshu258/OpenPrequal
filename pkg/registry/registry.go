package registry

// BackendRegistry defines the interface for backend management
// (listing, adding, removing, etc.)
type BackendRegistry interface {
	ListBackends() []string
	RegisterBackend(url string)
	RemoveBackend(url string)
}

type InMemoryBackendRegistry struct {
	backends []string
}

func NewInMemoryBackendRegistry(backends []string) *InMemoryBackendRegistry {
	return &InMemoryBackendRegistry{backends: backends}
}

func (r *InMemoryBackendRegistry) ListBackends() []string {
	return r.backends
}

func (r *InMemoryBackendRegistry) RegisterBackend(url string) {
	for _, b := range r.backends {
		if b == url {
			return // already registered
		}
	}
	r.backends = append(r.backends, url)
}

func (r *InMemoryBackendRegistry) RemoveBackend(url string) {
	newBackends := make([]string, 0, len(r.backends))
	for _, b := range r.backends {
		if b != url {
			newBackends = append(newBackends, b)
		}
	}
	r.backends = newBackends
}
