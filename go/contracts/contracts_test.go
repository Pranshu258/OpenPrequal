package contracts

import "testing"

func TestBackendEqual(t *testing.T) {
	p := 8080
	a := NewBackend("http://a", &p)
	b := NewBackend("http://a", &p)
	if !a.Equal(b) {
		t.Fatalf("expected equal backends")
	}

	c := NewBackend("http://b", nil)
	if a.Equal(c) {
		t.Fatalf("expected not equal")
	}
}
