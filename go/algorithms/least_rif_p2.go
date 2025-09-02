package algorithms

import (
	"math/rand"
	"openprequal/abstractions"
	"openprequal/contracts"
)

type LeastRIFP2 struct{ reg abstractions.Registry }

func NewLeastRIFP2(r abstractions.Registry) *LeastRIFP2 { return &LeastRIFP2{reg: r} }
func (l *LeastRIFP2) Next() *contracts.Backend {
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
	if b1.InFlightRequests <= b2.InFlightRequests {
		return &b1
	}
	return &b2
}
