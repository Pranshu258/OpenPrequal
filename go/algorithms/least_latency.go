package algorithms

import (
	"openprequal/abstractions"
	"openprequal/contracts"
)

type LeastLatencyLB struct{ reg abstractions.Registry }

func NewLeastLatencyLB(r abstractions.Registry) *LeastLatencyLB { return &LeastLatencyLB{reg: r} }
func (l *LeastLatencyLB) Next() *contracts.Backend {
	list := l.reg.ListBackends()
	var best *contracts.Backend
	for _, b := range list {
		if !b.Health {
			continue
		}
		if best == nil || b.AvgLatency < best.AvgLatency {
			bb := b
			best = &bb
		}
	}
	return best
}
