package abstractions

import (
	"openprequal/contracts"
	"sync"
)

// Registry is an interface for registering and listing backends.
type Registry interface {
	Register(b contracts.Backend)
	Unregister(b contracts.Backend)
	ListBackends() []contracts.Backend
}

// NewInMemoryRegistry creates a simple in-memory registry.
func NewInMemoryRegistry() *InMemoryRegistry {
	return &InMemoryRegistry{backends: make([]contracts.Backend, 0)}
}

// InMemoryRegistry is a thread-safe in-memory implementation of Registry.
type InMemoryRegistry struct {
	mu       sync.Mutex
	backends []contracts.Backend
}

// Register adds a backend to the registry.
func (r *InMemoryRegistry) Register(b contracts.Backend) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.backends = append(r.backends, b)
}

// Unregister removes backends that match url and port.
func (r *InMemoryRegistry) Unregister(b contracts.Backend) {
	r.mu.Lock()
	defer r.mu.Unlock()
	out := r.backends[:0]
	for _, be := range r.backends {
		if be.Equal(&b) {
			continue
		}
		out = append(out, be)
	}
	r.backends = out
}

// ListBackends returns a copy of backends.
func (r *InMemoryRegistry) ListBackends() []contracts.Backend {
	r.mu.Lock()
	defer r.mu.Unlock()
	copyOut := make([]contracts.Backend, len(r.backends))
	copy(copyOut, r.backends)
	return copyOut
}

// ModelDump returns a map representation of the backend (rough parity with Python model_dump())
// ModelDump now lives on contracts.Backend
