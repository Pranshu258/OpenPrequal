package test

import (
	"reflect"
	"testing"

	"github.com/Pranshu258/OpenPrequal/cmd/proxy/internal/registry"
)

func TestInMemoryBackendRegistry_ListBackends(t *testing.T) {
	backends := []string{"http://localhost:8081", "http://localhost:8082"}
	reg := registry.NewInMemoryBackendRegistry(backends)
	got := reg.ListBackends()
	if !reflect.DeepEqual(got, backends) {
		t.Errorf("ListBackends() = %v, want %v", got, backends)
	}
}
