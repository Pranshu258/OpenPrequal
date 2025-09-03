package loadbalancer

// LoadBalancer defines the interface for load balancing strategies
// (random, round robin, etc.)
type LoadBalancer interface {
	PickBackend() string
}
