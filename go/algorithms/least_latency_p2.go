package algorithms

import (
	"math/rand"
	"openprequal/abstractions"
	"openprequal/contracts"
)

type LeastLatencyP2 struct{ reg abstractions.Registry }

func NewLeastLatencyP2(r abstractions.Registry) *LeastLatencyP2 { return &LeastLatencyP2{reg: r} }
func (l *LeastLatencyP2) Next() *contracts.Backend {
	list := l.reg.ListBackends()
	healthy := make([]contracts.Backend, 0)
	for _, b := range list {
		if b.Health {
			healthy = append(healthy, b)
		}
	}
	if len(healthy) == 0 {
		return nil
	}
	if len(healthy) == 1 {
		return &healthy[0]
	}
	i := rand.Intn(len(healthy))
	j := rand.Intn(len(healthy))
	b1 := healthy[i]
	b2 := healthy[j]
	if b1.AvgLatency <= b2.AvgLatency {
		return &b1
	}
	return &b2
}
