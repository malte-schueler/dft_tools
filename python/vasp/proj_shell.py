
import itertools as it
import numpy as np
import vasp.atm.c_atm_dos as c_atm_dos

np.set_printoptions(suppress=True)

def issue_warning(message):
    """
    Issues a warning.
    """
    print
    print "  !!! WARNING !!!: " + message
    print

################################################################################
################################################################################
#
# class ProjectorShell
#
################################################################################
################################################################################
class ProjectorShell:
    """
    Container of projectors related to a specific shell.

    The constructor pre-selects a subset of projectors according to
    the shell parameters passed from the config-file.

    Parameters:

    - sh_pars (dict) : shell parameters from the config-file
    - proj_raw (numpy.array) : array of raw projectors

    """
    def __init__(self, sh_pars, proj_raw, proj_params, nc_flag):
        self.lorb = sh_pars['lshell']
        self.ion_list = sh_pars['ion_list']
        self.user_index = sh_pars['user_index']
        self.nc_flag = nc_flag
#        try:
#            self.tmatrix = sh_pars['tmatrix']
#        except KeyError:
#            self.tmatrix = None

        self.lm1 = self.lorb**2
        self.lm2 = (self.lorb+1)**2

        self.ndim = self.extract_tmatrices(sh_pars)
#        if self.tmatrix is None:
#            self.ndim = self.lm2 - self.lm1
#        else:
## TODO: generalize this to a tmatrix for every ion
#            self.ndim = self.tmatrix.shape[0]

# Pre-select a subset of projectors (this should be an array view => no memory is wasted)
# !!! This sucks but I have to change the order of 'ib' and 'ilm' indices here
# This should perhaps be done right after the projector array is read from PLOCAR
#        self.proj_arr = proj_raw[self.ion_list, :, :, :, self.lm1:self.lm2].transpose((0, 1, 2, 4, 3))
# We want to select projectors from 'proj_raw' and form an array
#   self.proj_arr[nion, ns, nk, nlm, nb]
# TODO: think of a smart way of copying the selected projectors
#       perhaps, by redesigning slightly the structure of 'proj_arr' and 'proj_win'
#       or by storing only a mapping between site/orbitals and indices of 'proj_raw'
#        iproj_l = []
        nion = len(self.ion_list)
        nlm = self.lm2 - self.lm1
        _, ns, nk, nb = proj_raw.shape
        self.proj_arr = np.zeros((nion, ns, nk, nlm, nb), dtype=np.complex128)
        for io, ion in enumerate(self.ion_list):
            for m in xrange(nlm):
# Here we search for the index of the projector with the given isite/l/m indices
                for ip, par in enumerate(proj_params):
                    if par['isite'] - 1 == ion and par['l'] == self.lorb and par['m'] == m:
#                        iproj_l.append(ip)
                        self.proj_arr[io, :, :, m, :] = proj_raw[ip, :, :, :]
                        break

#        self.proj_arr = proj_raw[iproj_l, :, :, :].transpose((1, 2, 0, 3))

################################################################################
#
# extract_tmatrices
#
################################################################################
    def extract_tmatrices(self, sh_pars):
        """
        Extracts and interprets transformation matrices provided by the
        config-parser.
        There are two relevant options in 'sh_pars':

          'tmatrix'  : a transformation matrix applied to all ions in the shell
          'tmatrices': interpreted as a set of transformation matrices for each ion.

        If both of the options are present a warning is issued and 'tmatrices'
        supersedes 'tmatrix'.
        """
        nion = len(self.ion_list)
        nm = self.lm2 - self.lm1

        if 'tmatrices' in sh_pars:
            if 'tmatrix' in sh_pars:
                mess = "Both TRANSFORM and TRANSFILE are specified, TRANSFORM will be ignored."
                issue_warning(mess)

            raw_matrices = sh_pars['tmatrices']
            nrow, ncol = raw_matrices.shape

            assert nrow%nion == 0, "Number of rows in TRANSFILE must be divisible by the number of ions"
            assert ncol%nm == 0, "Number of columns in TRANSFILE must be divisible by the number of orbitals 2*l + 1"

            nr = nrow / nion
            nsize = ncol / nm
            assert nsize in (1, 2, 4), "Number of columns in TRANSFILE must be divisible by either 1, 2, or 4"
#
# Determine the spin-dimension and whether the matrices are real or complex
#
#            if nsize == 1 or nsize == 2:
# Matrices (either real or complex) are spin-independent
#                nls_dim = nm
#                if msize == 2:
#                    is_complex = True
#                else:
#                    is_complex = False
#            elif nsize = 4:
# Matrices are complex and spin-dependent
#                nls_dim = 2 * nm
#                is_complex = True
#
            is_complex = nsize > 1
            ns_dim = max(1, nsize / 2)

# Dimension of the orbital subspace
            assert nr%ns_dim == 0, "Number of rows in TRANSFILE is not compatible with the spin dimension"
            ndim = nr / ns_dim

            self.tmatrices = np.zeros((nion, nr, nm * ns_dim), dtype=np.complex128)

            if is_complex:
                raw_matrices = raw_matrices[:, ::2] + raw_matrices[:, 1::2] * 1j

            for io in xrange(nion):
                i1 = io * nr
                i2 = (io + 1) * nr
                self.tmatrices[io, :, :] = raw_matrices[i1:i2, :]

            return ndim

        if 'tmatrix' in sh_pars:
            raw_matrix = sh_pars['tmatrix']
            nrow, ncol = raw_matrix.shape

            assert ncol%nm == 0, "Number of columns in TRANSFORM must be divisible by the number of orbitals 2*l + 1"

# Only spin-independent matrices are expected here
            nsize = ncol / nm
            assert nsize in (1, 2), "Number of columns in TRANSFORM must be divisible by either 1 or 2"

            is_complex = nsize > 1
            if is_complex:
                matrix = raw_matrix[:, ::2] + raw_matrix[:, 1::2] * 1j
            else:
                matrix = raw_matrix

            ndim = nrow

            self.tmatrices = np.zeros((nion, nrow, nm), dtype=np.complex128)
            for io in xrange(nion):
                self.tmatrices[io, :, :] = raw_matrix

            return ndim

# If no transformation matrices are provided define a default one
        ns_dim = 2 if self.nc_flag else 1
        ndim = nm * ns_dim

        self.tmatrices = np.zeros((nion, ndim, ndim), dtype=np.complex128)
        for io in xrange(nion):
            self.tmatrices[io, :, :] = np.identity(ndim, dtype=np.complex128)

        return ndim

################################################################################
#
# select_projectors
#
################################################################################
    def select_projectors(self, ib_win, ib_min, ib_max):
        """
        Selects a subset of projectors corresponding to a given energy window.
        """
        self.ib_win = ib_win
        self.ib_min = ib_min
        self.ib_max = ib_max
        nb_max = ib_max - ib_min + 1

# Set the dimensions of the array
        nion, ns, nk, nlm, nbtot = self.proj_arr.shape
# !!! Note that the order of the two last indices is different !!!
        self.proj_win = np.zeros((nion, ns, nk, nlm, nb_max), dtype=np.complex128)

# Select projectors for a given energy window
        ns_band = self.ib_win.shape[1]
        for isp in xrange(ns):
            for ik in xrange(nk):
# TODO: for non-collinear case something else should be done here
                is_b = min(isp, ns_band)
                ib1 = self.ib_win[ik, is_b, 0]
                ib2 = self.ib_win[ik, is_b, 1] + 1
                ib_win = ib2 - ib1
                self.proj_win[:, isp, ik, :, :ib_win] = self.proj_arr[:, isp, ik, :, ib1:ib2]

################################################################################
#
# density_matrix
#
################################################################################
    def density_matrix(self, el_struct, site_diag=True, spin_diag=True):
        """
        Returns occupation matrix/matrices for the shell.
        """
        nion, ns, nk, nlm, nbtot = self.proj_win.shape

        assert site_diag, "site_diag = False is not implemented"
        assert spin_diag, "spin_diag = False is not implemented"

        occ_mats = np.zeros((ns, nion, nlm, nlm), dtype=np.float64)
        overlaps = np.zeros((ns, nion, nlm, nlm), dtype=np.float64)

#        self.proj_win = np.zeros((nion, ns, nk, nlm, nb_max), dtype=np.complex128)
        kweights = el_struct.kmesh['kweights']
        occnums = el_struct.ferw
        ib1 = self.ib_min
        ib2 = self.ib_max + 1
        for isp in xrange(ns):
            for ik, weight, occ in it.izip(it.count(), kweights, occnums[isp, :, :]):
                for io in xrange(nion):
                    proj_k = self.proj_win[io, isp, ik, ...]
                    occ_mats[isp, io, :, :] += np.dot(proj_k * occ[ib1:ib2],
                                                 proj_k.conj().T).real * weight
                    overlaps[isp, io, :, :] += np.dot(proj_k,
                                                 proj_k.conj().T).real * weight

#        if not symops is None:
#            occ_mats = symmetrize_matrix_set(occ_mats, symops, ions, perm_map)

        return occ_mats, overlaps

################################################################################
#
# density_of_states
#
################################################################################
    def density_of_states(self, el_struct, emesh):
        """
        Returns projected DOS for the shell.
        """
        nion, ns, nk, nlm, nbtot = self.proj_win.shape

# There is a problem with data storage structure of projectors that will
# make life more complicated. The problem is that band-indices of projectors
# for different k-points do not match because we store 'nb_max' values starting
# from 0.
        nb_max = self.ib_max - self.ib_min + 1
        ns_band = self.ib_win.shape[1]

        ne = len(emesh)
        dos = np.zeros((ne, ns, nion, nlm))
        w_k = np.zeros((nk, nb_max, ns, nion, nlm), dtype=np.complex128)
        for isp in xrange(ns):
            for ik in xrange(nk):
                is_b = min(isp, ns_band)
                ib1 = self.ib_win[ik, is_b, 0]
                ib2 = self.ib_win[ik, is_b, 1] + 1
                for ib_g in xrange(ib1, ib2):
                    for io in xrange(nion):
# Note the difference between 'ib' and 'ibn':
#  'ib'  counts from 0 to 'nb_k - 1'
#  'ibn' counts from 'ib1 - ib_min' to 'ib2 - ib_min'
                        ib = ib_g - ib1
                        ibn = ib_g - self.ib_min
                        proj_k = self.proj_win[io, isp, ik, :, ib]
                        w_k[ik, ib, isp, io, :] = proj_k * proj_k.conj()

#        eigv_ef = el_struct.eigvals[ik, ib, isp] - el_struct.efermi
        itt = el_struct.kmesh['itet'].T
# k-indices are starting from 0 in Python
        itt[1:, :] -= 1
        for isp in xrange(ns):
            for ib, eigk in enumerate(el_struct.eigvals[:, self.ib_min:self.ib_max+1, isp].T):
                for ie, e in enumerate(emesh):
                    eigk_ef = eigk - el_struct.efermi
                    cti = c_atm_dos.dos_weights_3d(eigk_ef, e, itt)
                    for im in xrange(nlm):
                        for io in xrange(nion):
                            dos[ie, isp, io, im] += np.sum((cti * w_k[itt[1:, :], ib, isp, io, im].real).sum(0) * itt[0, :])

        dos *= 2 * el_struct.kmesh['volt']
#        for isp in xrange(ns):
#            for ik, weight, occ in it.izip(it.count(), kweights, occnums[isp, :, :]):
#                for io in xrange(nion):
#                    proj_k = self.proj_win[isp, io, ik, ...]
#                    occ_mats[isp, io, :, :] += np.dot(proj_k * occ[ib1:ib2],
#                                                 proj_k.conj().T).real * weight
#                    overlaps[isp, io, :, :] += np.dot(proj_k,
#                                                 proj_k.conj().T).real * weight

#        if not symops is None:
#            occ_mats = symmetrize_matrix_set(occ_mats, symops, ions, perm_map)

        return dos


