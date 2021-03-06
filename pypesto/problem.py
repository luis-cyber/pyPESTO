"""
Problem
=======

A problem contains the objective as well as all information like prior
describing the problem to be solved.

"""

import numpy as np
import pandas as pd
import numbers
import copy

from typing import Iterable, List, Optional, Union

from .objective import ObjectiveBase
from .objective.priors import NegLogPriors


class Problem:
    """
    The problem formulation. A problem specifies the objective function,
    boundaries and constraints, parameter guesses as well as the parameters
    which are to be optimized.

    Parameters
    ----------
    objective:
        The objective function for minimization. Note that a shallow copy
        is created.
    lb, ub:
        The lower and upper bounds. For unbounded directions set to inf.
    dim_full:
        The full dimension of the problem, including fixed parameters.
    x_fixed_indices:
        Vector containing the indices (zero-based) of parameter components
        that are not to be optimized.
    x_fixed_vals:
        Vector of the same length as x_fixed_indices, containing the values
        of the fixed parameters.
    x_guesses:
        Guesses for the parameter values, shape (g, dim), where g denotes the
        number of guesses. These are used as start points in the optimization.
    x_names:
        Parameter names that can be optionally used e.g. in visualizations.
        If objective.get_x_names() is not None, those values are used,
        else the values specified here are used if not None, otherwise
        the variable names are set to ['x0', ... 'x{dim_full}']. The list
        must always be of length dim_full.
    x_scales:
        Parameter scales can be optionally given and are used e.g. in
        visualisation and prior generation. Currently the scales 'lin',
        'log`and 'log10' are supported.
    x_priors_defs:
        Definitions of priors for parameters. Types of priors, and their
        required and optional parameters, are described in the `Prior` class.
    dim:
        The number of non-fixed parameters.
        Computed from the other values.
    x_free_indices: array_like of int
        Vector containing the indices (zero-based) of free parameters
        (complimentary to x_fixed_indices).

    Notes
    -----

    On the fixing of parameter values:

    The number of parameters dim_full the objective takes as input must
    be known, so it must be either lb a vector of that size, or dim_full
    specified as a parameter.

    All vectors are mapped to the reduced space of dimension dim in __init__,
    regardless of whether they were in dimension dim or dim_full before. If
    the full representation is needed, the methods get_full_vector() and
    get_full_matrix() can be used.
    """

    def __init__(self,
                 objective: ObjectiveBase,
                 lb: Union[np.ndarray, List[float]],
                 ub: Union[np.ndarray, List[float]],
                 dim_full: Optional[int] = None,
                 x_fixed_indices: Optional[Iterable[int]] = None,
                 x_fixed_vals: Optional[Iterable[float]] = None,
                 x_guesses: Optional[Iterable[float]] = None,
                 x_names: Optional[Iterable[str]] = None,
                 x_scales: Optional[Iterable[str]] = None,
                 x_priors_defs: Optional[NegLogPriors] = None):
        self.objective = copy.deepcopy(objective)

        self.lb_full = np.array(lb).flatten()
        self.ub_full = np.array(ub).flatten()

        self.dim_full = dim_full if dim_full is not None else self.lb_full.size

        if x_fixed_indices is None:
            x_fixed_indices = []
        self.x_fixed_indices: List[int] = [int(ix) for ix in x_fixed_indices]

        # We want the fixed values to be a list, since we might need to add
        # or remove values during profile computation
        if x_fixed_vals is None:
            x_fixed_vals = []
        if isinstance(x_fixed_vals, numbers.Real):
            x_fixed_vals = [x_fixed_vals]
        self.x_fixed_vals: List[float] = [float(x) for x in x_fixed_vals]

        self._x_free_indices: Union[List[int], None] = None

        if x_guesses is None:
            x_guesses = np.zeros((0, self.dim_full))
        self.x_guesses_full: np.ndarray = np.array(x_guesses)

        if objective.x_names is not None:
            x_names = objective.x_names
        elif x_names is None:
            x_names = [f'x{j}' for j in range(0, self.dim_full)]
        self.x_names: List[str] = list(x_names)

        if x_scales is None:
            x_scales = ['lin'] * self.dim_full
        self.x_scales = x_scales

        self.x_priors = x_priors_defs

        self.normalize()

    @property
    def lb(self) -> np.ndarray:
        return self.lb_full[self.x_free_indices]

    @property
    def ub(self) -> np.ndarray:
        return self.ub_full[self.x_free_indices]

    @property
    def x_guesses(self) -> np.ndarray:
        return self.x_guesses_full[:, self.x_free_indices]

    @property
    def dim(self) -> int:
        return self.dim_full - len(self.x_fixed_indices)

    @property
    def x_free_indices(self) -> List[int]:
        return sorted(set(range(0, self.dim_full)) - set(self.x_fixed_indices))

    def normalize(self) -> None:
        """
        Reduce all vectors to dimension dim and have the objective accept
        vectors of dimension dim.
        """

        if self.lb_full.size == 1:
            self.lb_full = self.lb_full * np.ones(self.dim_full)
        elif self.lb_full.size != self.dim_full:
            self.lb_full = np.empty(self.dim_full)
            self.lb_full[self.x_free_indices] = self.lb
            self.lb_full[self.x_fixed_indices] = self.x_fixed_vals

        if self.ub_full.size == 1:
            self.ub_full = self.ub_full * np.ones(self.dim_full)
        elif self.ub_full.size != self.dim_full:
            self.ub_full = np.empty(self.dim_full)
            self.ub_full[self.x_free_indices] = self.ub
            self.ub_full[self.x_fixed_indices] = self.x_fixed_vals

        if self.x_guesses_full.shape[1] != self.dim_full:
            x_guesses = np.empty((self.x_guesses_full.shape[0], self.dim_full))
            x_guesses[:] = np.nan
            x_guesses[:, self.x_free_indices] = self.x_guesses_full
            self.x_guesses_full = x_guesses

        # make objective aware of fixed parameters
        self.objective.update_from_problem(
            dim_full=self.dim_full,
            x_free_indices=self.x_free_indices,
            x_fixed_indices=self.x_fixed_indices,
            x_fixed_vals=self.x_fixed_vals)

        # sanity checks
        if self.lb_full.size != self.dim_full:
            raise AssertionError("lb_full dimension invalid.")
        if self.ub_full.size != self.dim_full:
            raise AssertionError("ub_full dimension invalid.")
        if len(self.x_scales) != self.dim_full:
            raise AssertionError("x_scales dimension invalid.")
        if len(self.x_names) != self.dim_full:
            raise AssertionError("x_names must be of length dim_full.")
        if len(self.x_fixed_indices) != len(self.x_fixed_vals):
            raise AssertionError(
                "x_fixed_indices and x_fixed_vals musti have the same length."
            )

    def fix_parameters(
            self,
            parameter_indices: Union[Iterable[int], int],
            parameter_vals: Union[Iterable[float], float]) -> None:
        """
        Fix specified parameters to specified values
        """
        if not isinstance(parameter_indices, list):
            parameter_indices = [parameter_indices]

        if not isinstance(parameter_vals, list):
            parameter_vals = [parameter_vals]

        # first clean to-be-fixed indices to avoid redundancies
        for i_index, i_parameter in enumerate(parameter_indices):
            # check if parameter was already fixed, otherwise add it to the
            # fixed parameters
            if i_parameter in self.x_fixed_indices:
                self.x_fixed_vals[
                    self.x_fixed_indices.index(i_parameter)] = \
                    parameter_vals[i_index]
            else:
                self.x_fixed_indices.append(i_parameter)
                self.x_fixed_vals.append(parameter_vals[i_index])

        self.normalize()

    def unfix_parameters(
            self,
            parameter_indices: Union[Iterable[int], int]) -> None:
        """
        Free specified parameters
        """

        # check and adapt input
        if not isinstance(parameter_indices, list):
            parameter_indices = [parameter_indices]

        # first clean to-be-freed indices
        for i_parameter in parameter_indices:
            if i_parameter in self.x_fixed_indices:
                i_index = self.x_fixed_indices.index(i_parameter)
                self.x_fixed_indices.pop(i_index)
                self.x_fixed_vals.pop(i_index)

        self.normalize()

    def get_full_vector(
            self,
            x: Union[np.ndarray, None],
            x_fixed_vals: Iterable[float] = None
    ) -> Union[np.ndarray, None]:
        """
        Map vector from dim to dim_full. Usually used for x, grad.

        Parameters
        ----------
        x: array_like, shape=(dim,)
            The vector in dimension dim.
        x_fixed_vals: array_like, ndim=1, optional
            The values to be used for the fixed indices. If None, then nans are
            inserted. Usually, None will be used for grad and
            problem.x_fixed_vals for x.
        """
        if x is None:
            return None

        # make sure it is an array
        x = np.array(x)

        if len(x) == self.dim_full:
            return x

        # Note: The funny indexing construct is to handle residual gradients,
        # where the last dimension is assumed to be the parameter one.
        x_full = np.zeros(x.shape[:-1] + (self.dim_full,))
        x_full[:] = np.nan
        x_full[..., self.x_free_indices] = x
        if x_fixed_vals is not None:
            x_full[..., self.x_fixed_indices] = x_fixed_vals
        return x_full

    def get_full_matrix(
            self, x: Union[np.ndarray, None]
    ) -> Union[np.ndarray, None]:
        """
        Map matrix from dim to dim_full. Usually used for hessian.

        Parameters
        ----------
        x: array_like, shape=(dim, dim)
            The matrix in dimension dim.
        """
        if x is None:
            return None

        # make sure it is an array
        x = np.array(x)

        if len(x) == self.dim_full:
            return x

        x_full = np.zeros((self.dim_full, self.dim_full))
        x_full[:, :] = np.nan
        x_full[np.ix_(self.x_free_indices, self.x_free_indices)] = x

        return x_full

    def get_reduced_vector(
            self, x_full: Union[np.ndarray, None]
    ) -> Union[np.ndarray, None]:
        """
        Map vector from dim_full to dim, i.e. delete fixed indices.

        Parameters
        ----------
        x_full: array_like, ndim=1
            The vector in dimension dim_full.
        """
        if x_full is None:
            return None

        if len(x_full) == self.dim:
            return x_full

        x = [x_full[idx] for idx in self.x_free_indices]
        return np.array(x)

    def get_reduced_matrix(
            self, x_full: Union[np.ndarray, None]
    ) -> Union[np.ndarray, None]:
        """
        Map matrix from dim_full to dim, i.e. delete fixed indices.

        Parameters
        ----------
        x_full: array_like, ndim=2
            The matrix in dimension dim_full.
        """
        if x_full is None:
            return None

        if len(x_full) == self.dim:
            return x_full

        x = x_full[np.ix_(self.x_free_indices, self.x_free_indices)]

        return x

    def full_index_to_free_index(self, full_index: int):
        """Calculate index in reduced vector from index in full vector.

        Parameters
        ----------
        full_index: The index in the full vector.

        Returns
        -------
        free_index: The index in the free vector.
        """
        fixed_indices = np.asarray(self.x_fixed_indices)
        if full_index in fixed_indices:
            raise ValueError(
                "Cannot compute index in free vector: Index is fixed.")
        return full_index - sum(fixed_indices < full_index)

    def print_parameter_summary(self) -> None:
        """
        Prints a summary of what parameters are being optimized and
        parameter boundaries.
        """
        print(  # noqa: T001 (print)
            pd.DataFrame(
                index=self.x_names,
                data={
                    'free': [idx in self.x_free_indices
                             for idx in range(self.dim_full)],
                    'lb_full': self.lb_full,
                    'ub_full': self.ub_full
                }
            )
        )
