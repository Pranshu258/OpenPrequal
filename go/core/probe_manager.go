package core

import (
	"context"
	"time"
)

type ProbeManager struct {
	pool          *ProbePool
	queue         *ProbeTaskQueue
	endpoint      string
	maxConcurrent int
	cancel        context.CancelFunc
}

func NewProbeManager(pool *ProbePool, queue *ProbeTaskQueue, endpoint string, maxConcurrent int) *ProbeManager {
	return &ProbeManager{pool: pool, queue: queue, endpoint: endpoint, maxConcurrent: maxConcurrent}
}

func (p *ProbeManager) Run(ctx context.Context) {
	ctx, cancel := context.WithCancel(ctx)
	p.cancel = cancel
	go func() {
		for {
			select {
			case <-ctx.Done():
				return
			default:
				id := p.queue.GetTask()
				if id == nil {
					time.Sleep(100 * time.Millisecond)
					continue
				}
				// in full implementation we'd perform HTTP probe; here we simulate
				p.pool.AddProbe(*id, 0.01, 0.0)
			}
		}
	}()
}

func (p *ProbeManager) Stop() {
	if p.cancel != nil {
		p.cancel()
	}
}
