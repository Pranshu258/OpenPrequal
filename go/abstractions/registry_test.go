package abstractions

import (
	"openprequal/contracts"
	"testing"
)

func TestInMemoryRegistry_RegisterUnregisterList(t *testing.T) {
	r := NewInMemoryRegistry()
	p1 := 80
	p2 := 8080
	r.Register(contracts.Backend{URL: "http://a", Port: &p1, Health: true})
	r.Register(contracts.Backend{URL: "http://b", Port: &p2, Health: true})

	list := r.ListBackends()
	if len(list) != 2 {
		t.Fatalf("expected 2 backends, got %d", len(list))
	}

	r.Unregister(contracts.Backend{URL: "http://a", Port: &p1})
	list = r.ListBackends()
	if len(list) != 1 {
		t.Fatalf("expected 1 backend after unregister, got %d", len(list))
	}
	if list[0].URL != "http://b" {
		t.Fatalf("expected remaining backend to be http://b, got %s", list[0].URL)
	}
}
