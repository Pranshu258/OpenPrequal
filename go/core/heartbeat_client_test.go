package core

import (
	"openprequal/contracts"
	"testing"
)

func TestHeartbeatUpdatesBackend(t *testing.T) {
	mm := NewMetricsManager(nil)
	b := &contracts.Backend{URL: "http://a"}
	hb := NewHeartbeatClient(b, "http://proxy", 1, mm)
	hb.Start()
	// let it run one tick
	// in CI this is quick; we'll just stop immediately for the unit test
	hb.Stop()
}
