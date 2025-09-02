package core

import "testing"

func TestProbePoolAddGet(t *testing.T) {
	p := NewProbePool()
	p.AddProbe("b1", 0.05, 1)
	lat := p.GetCurrentLatency("b1")
	if lat == nil {
		t.Fatalf("expected latency")
	}
}
