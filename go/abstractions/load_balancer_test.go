package abstractions

import (
	"openprequal/contracts"
	"testing"
)

func TestRoundRobinNextBackend(t *testing.T) {
	r := NewInMemoryRegistry()
	p1 := 80
	p2 := 80
	r.Register(contracts.Backend{URL: "http://a", Port: &p1, Health: true})
	r.Register(contracts.Backend{URL: "http://b", Port: &p2, Health: true})
	lb := NewRoundRobin(r)

	b1 := lb.NextBackend()
	if b1 == nil || b1.URL != "http://a" {
		t.Fatalf("expected first backend http://a got %v", b1)
	}
	b2 := lb.NextBackend()
	if b2 == nil || b2.URL != "http://b" {
		t.Fatalf("expected second backend http://b got %v", b2)
	}
	b3 := lb.NextBackend()
	if b3 == nil || b3.URL != "http://a" {
		t.Fatalf("expected third backend http://a got %v", b3)
	}
}
