"""Provides classes for pyBA. """

import numpy as np
from numpy.linalg import solve, cholesky, eigh


# Exception classes for error handling
class ZeroException(Exception):
    pass


class SamplingException(Exception):
    pass


class ShapeException(Exception):
    pass


# Main pyBA classes
class Bgmap:
    """ Background mapping structure.
    """

    __author__ = "Berian James"
    __version__ = "0.3"
    __email__ = "berian@berkeley.edu"

    def __init__(self,
                 dx=np.array([0.,0.]),
                 theta=0.,
                 d0=np.array([0.,0.]),
                 L = np.array([1.,1.]),
                 mu = np.empty((7,)) + np.nan,
                 sigma = np.zeros(7) + np.inf ):

        # Define central likelihood value
        if np.isnan(mu).any():
            self.mu = np.array([ dx[0], dx[1], theta, d0[0], d0[1], L[0], L[1] ])
        else:
            self.mu = mu

        # Define covariance matrix
        if sigma.ndim == 1:
            self.sigma = np.diag(sigma)
        else:
            self.sigma = sigma

        # Define parameter handles for convenience
        self.dx = self.mu[0:2]
        self.theta = self.mu[2]
        self.d0 = self.mu[3:5]
        self.L = self.mu[5:7]

        return

    def llik(self,P=np.array( [0., 0., 0., 0., 0., 1., 1.] ) ):
        """ Compute log-likelihood of parameter set P within 
        likelihood distribution bgmap object.
        """

        delta = self.mu - P
        sigma = self.sigma.copy()

        # Interpret infs in covariance matrix as contributing
        #  zero to the chi^2 (set delta[i] = 0).
        I = np.nonzero(np.isinf(np.diag(sigma)))[0]
        delta[I] = 0
        sigma[I,:] = 0
        sigma[:,I] = 0
        sigma[I,I] = 1

        return -0.5 * delta.dot( solve( sigma, delta ) )

    def sample(self,n=1):
        """ Returns n samples from a Bgmap distribution.
        """
        # N.B.! Won't work with covariance matrices containings infs!
        
        #vals = np.zeros( (n,len(self.mu)) )
        stds = np.random.randn( 2,len(self.mu) )
        chol = cholesky(self.sigma)
        return [self.mu + np.dot( chol, stds[:,i] ).T for i in range(n)]
            
class Bivarg:
    """ Implements bivariate gaussian structure and routines to modify it.
    """

    __author__ = "Berian James"
    __version__ = "0.3"
    __email__ = "berian@berkeley.edu"

    def __init__(self,mu=np.array([0.,0.]),sigma=np.array([ [1.,0.],[0.,1.] ]),theta=0):

        # Set central location
        self.mu = np.squeeze(np.array(mu))

        # Parse input variance values
        if np.size(sigma) == 1:
            sigma = np.array([ [sigma, 0], [0, sigma] ])
        elif np.size(sigma) == 2:
            sigma = np.array([ [sigma[0],0], [0,sigma[1]] ])
        elif np.size(sigma) == 3:
            sigma = np.array([ [sigma[0], sigma[2]], [sigma[2], sigma[1]] ])
        elif np.shape(sigma) != (2,2):
            raise ShapeException('Covariance matrix should be specified as a 1-, 2- or 3-vector, or a 2x2 array')

        # Catch negative variances
        if sigma[0,0] < 0 or sigma[1,1] < 0:
            raise ZeroException('One or more specfied variances are less than zero.')

        # Handle points with zero uncertainty
        if sigma[0,0] + sigma[1,1] == 0:
            # Bivarg is actually a point. Note this and do not
            #  compute further distribution properties
            self.point = True
            self.sigma = np.array([[0,0],[0,0]])
            self.det = 0 
        
        else:
            # Bivarg is a distribution, not a point. 
            self.point = False

            self.E,self.V = eigh(np.array(sigma))
        
            self.E = np.diag(np.real(self.E))

            if theta!=0:
                U = np.array([ [np.cos(theta),-np.sin(theta)],
                               [np.sin(theta), np.cos(theta)] ])
                self.V = np.dot(U,self.V)

            self.sigma = np.dot( self.V, np.dot(self.E,self.V.T) )

            sigma = self.sigma
            self.det = sigma[0,0]*sigma[1,1] - sigma[0,1]*sigma[1,0]
            self.trace = sigma[0,0] + sigma[1,1]

            self.chol = np.array([ [np.sqrt(sigma[0,0]),0.],
                                   [sigma[0,1]/np.sqrt(sigma[0,0]), 
                                    np.sqrt( sigma[1,1]-sigma[1,0]*sigma[0,1]/sigma[0,0] ) ] ])

            self.theta = np.math.degrees(np.math.atan2(self.V[0,1],self.V[0,0]))

        return

    def __sub__(self,other):
        return Bivarg( mu=self.mu-other.mu, sigma=self.sigma+other.sigma )

    def __add__(self,other):
        return Bivarg( mu=self.mu+other.mu, sigma=self.sigma+other.sigma )

    def __repr__(self):
        """ Print beautiful representation of bivarg object.
        """
        reprstr = str(self.mu) + ' ' + str(self.sigma.ravel()[np.array([0, 3, 1])])
        return reprstr

    def __str__(self):
        """ Print more verbose representation of bivarg."""
        strstr = 'mu: ' + str(self.mu) + ', ' + \
            '[sxx syy]: ' + str(np.sqrt(self.sigma.ravel()[np.array([0,3])])) + ', ' + \
            'rho_xy: ' + str(self.sigma[0,1] / np.sqrt(self.sigma[0,0]*self.sigma[1,1]))
        return strstr

    def transform(self,P=Bgmap()):
        """ Maps a bivariate gaussian distribution (self) to another
        bivariate gaussian by translation (dmu), using a background mapping
        object, i.e., by scaling the principal axes (L) and rotating (theta)
        about a given point (d0).
        """

        # Prep inputs
        if P.__class__.__name__ == 'Bgmap':
            dmu = P.mu[0:2]
            theta = P.mu[2]
            d0 = P.mu[3:5]
            L = P.mu[5:7]    
        elif P.__class__.__name__ == 'ndarray':
            dmu = P[0:2]
            theta = P[2]
            d0 = P[3:5]
            L = P[5:7]
        else:
            raise TypeError('Argument to background mapping transform should be a Bgmap object or a 7-vector of parameters.')

        # Calculate transformed centre
        U = np.squeeze(np.array([ [np.cos(theta),-np.sin(theta)],
                                  [np.sin(theta), np.cos(theta)] ]))
        mu = np.dot(U,(self.mu * L + dmu) - d0) + d0

        # Calculate transformed covariance
        if self.point == True:
            # Object is a point; it has no covariance. So we copy
            #  the zero covariance array it already has.
            sigma = self.sigma

        else:
            L = np.diag(L)
            V = np.dot(U,self.V)
            E = np.dot(L,self.E)
            sigma = np.dot( V, np.dot(E,V.T) ) 
    
        # Create new bivarg object with transformed values
        return LittleBivarg(mu,sigma)

    def sample(self,n=1):
        """ Draw n samples from bivariate distribution M
        """

        if self.point == True:
            # Bivarg is actually a point, can't sample
            raise SamplingException('Distribution is a point; it cannot be sampled')
        
        else:
            vals = np.zeros( (n,2) )
            stds = np.random.randn(2,n)
            for i in range(0,n):
                vals[i] = self.mu + np.dot( self.chol, stds[:,i] ).T
            
        return vals

class LittleBivarg(Bivarg):
    """ This is a minimal bivarg class that is used for representing
    transformed Bivargs that are going to be thrown away later, but might
    be used for likelihood computations.
    """
    def __init__(self,mu=np.array([0.,0.]),sigma=np.array([ [1.,0.],[0.,1.] ])):
        self.mu = mu
        self.sigma = sigma
        self.det = sigma[0,0]*sigma[1,1] - sigma[1,0]*sigma[0,1]
        
        return

    def promote(self):
        """ Promotes a LitteBivarg to a full Bivarg. This might happen
        when a transformed Bivarg needs to be used for transformation in
        its own right.
        Good job LittleBivarg!
        """
        return Bivarg(mu=self.mu,sigma=self.sigma)

class Amap:
    """ Implements astrometric mapping class as a gaussian process.
    """

    __author__ = "Berian James"
    __version__ = "0.3"
    __email__ = "berian@berkeley.edu"

    def __init__(self,P,A,B,scale=100.0,amp=100.0*np.eye(2)):
        """ Create instance of astrometric map from a background mapping
        (Bgmap object P) and objects in each frame (Bivarg arrays A and B).
        """
        from pyBA.distortion import astrometry_cov, d2

        self.P = P
        self.A = A
        self.B = B

        # Default GP hyperparameters
        self.scale = scale
        self.amp = amp
        self.hyperparams = {'scale': self.scale, 'amp': self.amp}

        # Gather locations of inputs and build distance matrix
        self.xyarr = np.array([o.mu for o in self.A])
        self.d2 = d2(self.xyarr,self.xyarr)

        # Use measurement uncertainties of displacement as 'nugget'
        self.V = np.array([a.sigma for a in A]) + np.array([b.sigma for b in B])

        # Build covariance matrix for data points
        self.C = astrometry_cov(self.d2, self.scale, self.amp, var = self.V)

        # Don't compute cholesky decomposition of C until needed
        self.chol = None

        return 

    def draw_background(self, res=30):
        """ Method to draw maximum likelihood background mapping 
        on grid of given resolution."""

        from pyBA.plotting import draw_MAP_background
        draw_MAP_background(self.A, self.B, self.P, res = res )
        return

    def draw_realisation(self, res=30):
        """ Draw realisation from Dmap gaussian process and
        plot it on grid of given resolution."""

        from pyBA.plotting import draw_realisation

        # If GP is not conditioned (as checked by self.chol not yet computed),
        #  draw realisation without using input data
        if self.chol == None:
            draw_realisation(self.A, self.B, self.P, self.scale, 
                             self.amp, self.chol, res=res)

        # Otherwise, perform regression on observed data
        else:
            draw_realisation(self.A, self.B, self.P, self.scale, 
                             self.amp, self.chol, res=res)
            
        return

    def draw_residuals(self, res=30, scaled='no'):
        """ Draw residuals of object mappings between frames
        from background mapping."""

        from pyBA.plotting import draw_MAP_residuals
        draw_MAP_residuals(self.A, self.B, self.P, scaled=scaled)
        return

    def build_covariance(self,scale=None,amp=None):

        from pyBA.distortion import astrometry_cov
        
        if scale != None:
            self.scale = scale
            self.hyperparams['scale'] = scale

        if amp != None:
            if np.size(amp) == 1:
                amp = np.array([[amp,0.],[0.,amp]])
            elif np.size(amp) == 2:
                amp = np.array([[amp[0],amp[1]],[amp[1],amp[0]]])

            self.amp = amp
            self.hyperparams['amp'] = amp
        
        self.C = astrometry_cov(self.d2, self.scale, self.amp, var = self.V)

        # Compute cholesky decomposition of C with optimised parameters
        from scipy.linalg import cho_factor
        self.chol = cho_factor(self.C)

    def condition(self):
        """ Conditions hyper-parameters of gaussian process.
        """

        from pyBA.distortion import optimise_HP

        #HP0 = [self.scale, self.amp[0,0], self.amp[0,1]]
        HP0 = [self.scale, self.amp[0,0]]

        # Optimise hyperparameters
        ML_output = optimise_HP(self.A, self.B, self.P, HP0)
        scale_conditioned = ML_output[0]
        amp_conditioned = ML_output[1]
        #ML_lnprob = ML_output[2]

        # Rebuild covariance matrix with updated hyperparameters
        self.build_covariance(scale_conditioned, amp_conditioned)
        
        return ML_output

    def regression(self, xy):
        """Performs regression on a mapping object at some locations, 
        which can be points or distributions."""
        from scipy.linalg import cho_solve
        from pyBA.distortion import d2, astrometry_cov, compute_residual

        # Convert list of inputs to array if needed
        if type(xy) == list:
            xy = np.array(xy)

        # Parse input
        if type(xy)==np.ndarray:

            # Single point
            if xy.size == 2 and type(xy)==np.ndarray:
                XY = np.array([ Bivarg(mu=xy,sigma=0) ])

            # Array of points
            elif xy.ndim == 2 and type(xy[0])==np.ndarray:
                XY = np.array([ Bivarg(mu=xy[i],sigma=0) for i in range(len(xy)) ])

            # Array of query distributions
            elif type(xy[0].__class__.__name__=='Bivarg'):
                XY = xy

            else:
                raise TypeError('Regression input should be an nx2 array of coordinates, or an array of Bivarg distributions')

        # Single query distribution
        elif xy.__class__.__name__ == 'Bivarg':
            XY = np.array([ xy ])
            
        else:
            raise TypeError('Regression input should be an nx2 array of coordinates, or an array of Bivarg distributions')
        
        ## Gaussian process regression
        # Old grid coordinates
        xyobs = np.array([o.mu for o in self.A])

        # New grid coordinates
        xynew = np.array([o.mu for o in XY])

        # Get regression data (resdiual to background)
        dx, dy = compute_residual(self.A, self.B, self.P)
        dxy = np.array([dx, dy]).T.flatten()

        # Build cross covariance between old and new locations
        d2_grid = d2(xynew,xyobs)
        Cs = astrometry_cov(d2_grid, self.scale, self.amp)

        # Build covariance for new locations
        d2_grid = d2(xynew, xynew)
        Vnew = np.array([o.sigma for o in XY])
        # Don't need to add variances for input points here, they will be propagated
        #  through the background transformation.
        #Css = astrometry_cov(d2_grid, self.scale, self.amp, var=Vnew)
        Css = astrometry_cov(d2_grid, self.scale, self.amp)

        # Regression: mean function evaluated at new locations
        vxy = Cs.dot(cho_solve(self.chol, dxy)).reshape( (len(XY),2) )
        
        # Regression: uncertainties at new locations
        S = Css - Cs.dot(cho_solve(self.chol, Cs.T))

        ## Package output
        # Background (mean function) mapping
        R = np.array([o.transform(self.P) for o in XY])        

        # Add regression residuals to mean function
        munew = np.array([o.mu for o in R]) + vxy

        # Add regression uncertainty 
        Sdiag = np.array([S[i:i+2,i:i+2] for i in range(0,len(S),2)])
        sigmanew = np.array([o.sigma for o in R]) + Sdiag

        # Construct output array of Bivargs
        O = np.array([ Bivarg(mu=munew[i], sigma=sigmanew[i]) for i in range(len(R)) ])

        return O
