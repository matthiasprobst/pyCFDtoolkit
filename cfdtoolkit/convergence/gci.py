"""Grid convergence index (GCI)"""
from math import pow, log, fabs
from typing import Union, List

import numpy as np
import pyGCS


class GCISolution:
    """Interface for GCI solution"""

    def __init__(self, gci: pyGCS.GCI):
        self._gci = gci

    def __repr__(self):
        """TODO: use tabulate to print a nice table"""
        return f'GCI: {self.gci}'

    @property
    def gci(self):
        """Grid convergence index"""
        return self._gci.get('gci')

    @property
    def refinement_ratio(self):
        """Refinement ratio"""
        return self._gci.get('refinement_ratio')

    @property
    def apparent_order(self):
        """Apparent order"""
        return self._gci.get('apparent_order')

    @property
    def asymptotic_gci(self):
        """Asymptotic GCI"""
        return self._gci.get('asymptotic_gci')


class GCI:
    """Grid convergence index (GCI) interface class"""

    def __init__(self, cells, simulation_order, volume, dimension: int):
        """Grid convergence index (GCI)

        Parameters
        ----------
        cells : List[float] or np.ndarray
            Number of cells in each mesh
        simulation_order : float
            Order of the convergence
        volume: float
            Volume of the simulation domain
        dimension : int
            Dimension of the simulation. 2D or 3D.
        """
        self.cells = cells
        if dimension not in (2, 3):
            raise ValueError("Simulation dimension must be 2 or 3")
        self.dim = dimension
        self.volume = volume
        self.simulation_order = simulation_order

    def compute(self, solution: Union[List[float], np.ndarray]):
        """compute the GCI for given quantity
        Parameters
        ----------
        solution : List[float] or np.ndarray
            Solution for each mesh. Order must be corresponding to the order when initializing the class.
        """
        return GCISolution(pyGCS.GCI(dimension=self.dim,
                                     simulation_order=self.simulation_order,
                                     volume=self.volume,
                                     cells=self.cells,
                                     solution=solution))

    @staticmethod
    def compute_order(initial_order, e21, e32, r21, r32):
        """
        Compute the formal order of accuracy `p`.

        taken from
        https://github.com/tomrobin-teschner/pyGCS/blob/d3803f8bdd08d1dff703b4a5f2480bdadc862154/src/pyGCS/GCI.py#L109
        """
        eps = 1
        iteration = 1
        max_iteration = 100
        norm = 1
        p = initial_order
        while eps > 1e-6:
            p_old = p

            s = np.sign(e32 / e21)
            q = log((pow(r21, p) - s) / (pow(r32, p) - s))
            p = (1.0 / log(r21)) * fabs(log(fabs(e32 / e21)) + q)

            residual = p - p_old
            if iteration == 1:
                norm = residual
            iteration += 1
            eps = residual / norm
            if iteration == max_iteration:
                print('WARNING: max number of iterations (' + str(max_iteration) +
                      ') reached for calculating apparent order p ...')
                break
        return p


def main():
    cells = [18000, 8000, 4500]
    solutions = [6.063, 5.972, 5.863]

    gci = GCI(cells=cells,
              simulation_order=2, volume=76, dimension=2)
    print(gci.compute(solutions).gci)
    print(gci.compute(solutions).apparent_order)
    print(gci.compute(solutions).asymptotic_gci)
    print(gci.compute(solutions))

    from pyGCS import GCI as GCI2
    gci = GCI2(dimension=2,
               simulation_order=2,
               volume=76,
               cells=cells,
               solution=solutions)
    print(gci.get('gci'))

    gci.set('solution', [1, 2, 3])
    print(gci.get('gci'))

    gci.set('solution', solutions)
    print(gci.get('gci'))


if __name__ == "__main__":
    main()
