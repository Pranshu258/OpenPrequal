package core

import (
	"context"
	"testing"
)

func TestProbeManagerRun(t *testing.T) {
	pool := NewProbePool()
	q := NewProbeTaskQueue()
	q.AddTask("b1")
	pm := NewProbeManager(pool, q, "/probe", 2)
	ctx := context.Background()
	pm.Run(ctx)
	// allow some time to process
	pm.Stop()
}
