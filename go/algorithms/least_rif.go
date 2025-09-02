package algorithms

import (
	"openprequal/abstractions"
	"openprequal/contracts"
)

type LeastRIF struct{ reg abstractions.Registry }

func NewLeastRIF(r abstractions.Registry) *LeastRIF { return &LeastRIF{reg: r} }
func (l *LeastRIF) Next() *contracts.Backend {
	list := l.reg.ListBackends()
	var best *contracts.Backend
	for _, b := range list {
		if !b.Health {
			continue
		}
		if best == nil || b.InFlightRequests < best.InFlightRequests {
			bb := b
			best = &bb
		}
	}
	return best
}
