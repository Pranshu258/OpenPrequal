package core

import "testing"

func TestMetricsObserveAndAvg(t *testing.T) {
	mm := NewMetricsManager([]int{1, 5, 10})
	mm.IncInFlight()
	mm.RecordLatency(0.1)
	avg := mm.GetAvgLatency()
	if avg == 0.0 {
		t.Fatalf("expected non-zero avg")
	}
}
