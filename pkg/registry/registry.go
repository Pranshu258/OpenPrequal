package registry

// BackendRegistry defines the interface for backend management
// (listing, adding, removing, etc.)
type BackendRegistry interface {
	ListBackends() []string
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
