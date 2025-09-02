package core

import (
	"openprequal/contracts"
	"testing"
)

func TestBackendRegistryRegisterList(t *testing.T) {
	r := NewBackendRegistry(1)
	b := &contracts.Backend{URL: "http://a", Health: true}
	r.Register(b)
	list := r.ListBackends()
	if len(list) != 1 {
		t.Fatalf("expected 1 backend")
	}
}
