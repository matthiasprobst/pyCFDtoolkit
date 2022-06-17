from abc import ABC, abstractmethod

from ...typing import PATHLIKE


class CFXBoundaryCondition(ABC):

    @abstractmethod
    def write(self, hdf_filename: PATHLIKE, hdf_obj_path: str) -> None:
        """writes the boundary condition to file"""
        pass
