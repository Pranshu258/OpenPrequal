package test

import (
	"reflect"
	"testing"

	"github.com/Pranshu258/OpenPrequal/pkg/registry"
)

func TestInMemoryBackendRegistry_ListBackends(t *testing.T) {
	backends := []string{"http://localhost:8081", "http://localhost:8082"}
	reg := registry.NewInMemoryBackendRegistry(backends)
	got := reg.ListBackends()
	// convert []*BackendInfo -> []string of URLs for comparison
	urls := make([]string, 0, len(got))
	for _, b := range got {
		urls = append(urls, b.URL)
	}
	if !reflect.DeepEqual(urls, backends) {
		t.Errorf("ListBackends() = %v, want %v", urls, backends)
	}
}
