package algorithms

import (
	"testing"
	"time"

	"openprequal/abstractions"
	"openprequal/contracts"
	"openprequal/core"
)

// helper to register backends
func registerBackends(reg *abstractions.InMemoryRegistry, urls []string) []contracts.Backend {
	outs := make([]contracts.Backend, 0, len(urls))
	for _, u := range urls {
		b := contracts.NewBackend(u, nil)
		b.Health = true
		reg.Register(*b)
		outs = append(outs, *b)
	}
	return outs
}

func TestNextSelectsLowestLatencyWhenCold(t *testing.T) {
	reg := abstractions.NewInMemoryRegistry()
	pool := core.NewProbePool()
	tq := core.NewProbeTaskQueue()

	urls := []string{"b1", "b2", "b3"}
	registerBackends(reg, urls)

	// For each backend: create RIF history where last < median so they are classified cold
	// Also add latencies with different averages so we can assert selection.
	// b1 -> avg latency 10, b2 -> 20, b3 -> 30
	// RIF pattern: [100,100,1] -> last(1) < median(100) => cold
	for _, u := range urls {
		pool.AddProbe(u, 50.0, 100.0)
		pool.AddProbe(u, 50.0, 100.0)
		// small last latency to skew average differently per backend
	}
	// adjust last latencies per backend to create differing averages
	pool.AddProbe("b1", 0.0, 1.0)
	pool.AddProbe("b2", 10.0, 1.0)
	pool.AddProbe("b3", 20.0, 1.0)

	p := NewPrequal(reg, pool, tq)
	defer p.Stop()

	chosen := p.Next()
	if chosen == nil {
		t.Fatalf("expected a backend, got nil")
	}
	if chosen.URL != "b1" {
		t.Fatalf("expected b1 (lowest latency), got %s", chosen.URL)
	}
}

func TestNextSelectsLowestRIFWhenHot(t *testing.T) {
	reg := abstractions.NewInMemoryRegistry()
	pool := core.NewProbePool()
	tq := core.NewProbeTaskQueue()

	urls := []string{"h1", "h2", "h3"}
	registerBackends(reg, urls)

	// Create RIF histories where last >= median so they are hot.
	// We'll make last values: h1->5, h2->10, h3->20 so h1 should be selected.
	pool.AddProbe("h1", 10.0, 1.0)
	pool.AddProbe("h1", 10.0, 5.0)

	pool.AddProbe("h2", 10.0, 1.0)
	pool.AddProbe("h2", 10.0, 10.0)

	pool.AddProbe("h3", 10.0, 1.0)
	pool.AddProbe("h3", 10.0, 20.0)

	p := NewPrequal(reg, pool, tq)
	defer p.Stop()

	chosen := p.Next()
	if chosen == nil {
		t.Fatalf("expected a backend, got nil")
	}
	if chosen.URL != "h1" {
		t.Fatalf("expected h1 (lowest current RIF), got %s", chosen.URL)
	}
}

func TestScheduleProbeTasksForcesProbes(t *testing.T) {
	reg := abstractions.NewInMemoryRegistry()
	pool := core.NewProbePool()
	tq := core.NewProbeTaskQueue()

	urls := []string{"f1", "f2", "f3"}
	healthy := registerBackends(reg, urls)

	p := NewPrequal(reg, pool, tq)
	defer p.Stop()

	// ensure lastProbeTime is zero so forced probes will be scheduled
	// call scheduleProbeTasks directly
	p.scheduleProbeTasks(healthy)

	// allow goroutines to enqueue
	time.Sleep(20 * time.Millisecond)

	if tq.Size() == 0 {
		t.Fatalf("expected probe tasks to be scheduled, queue size 0")
	}
}
