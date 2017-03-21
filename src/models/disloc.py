import numpy as num

from kite import disloc_ext
from pyrocko.guts import Object, Float, List, Bool

d2r = num.pi / 180.
r2d = 180. / num.pi


class OkadaSource(Object):

    __implements__ = 'disloc'

    easting = Float.T(
        help='Easting in [m]')
    northing = Float.T(
        help='Northing in [m]')
    depth = Float.T(
        help='Depth in [m]')
    width = Float.T(
        help='Width, downdip in [m]')
    length = Float.T(
        help='Length in [m]')
    strike = Float.T(
        default=45.,
        help='Strike, clockwise from north in [deg]')
    dip = Float.T(
        default=45.,
        help='Dip, down from horizontal in [deg]')
    rake = Float.T(
        default=90.,
        help='Rake, clockwise in [deg]; 0 is left-lateral Strike-Slip')
    slip = Float.T(
        default=1.5,
        help='Slip in [m]')
    nu = Float.T(
        default=1.25,
        help='Material parameter Nu in P s^-1')
    opening = Float.T(
        help='Opening of the plane in [m]',
        optional=True,
        default=0.)

    def dislocSource(self, dsrc=None):
        if dsrc is None:
            dsrc = num.empty(10)

        if self.dip == 90.:
            dip = self.dip - 1e-5
        else:
            dip = self.dip

        dsrc[0] = self.length
        dsrc[1] = self.width
        dsrc[2] = self.depth
        dsrc[3] = -dip  # Dip
        dsrc[4] = self.strike
        dsrc[5] = self.easting
        dsrc[6] = self.northing

        ss_slip = num.cos(self.rake * d2r) * self.slip
        ds_slip = num.sin(self.rake * d2r) * self.slip
        # print '{:<13}{}\n{:<13}{}'.format(
        #     'strike_slip', ss_slip, 'dip_slip', ds_slip)
        dsrc[7] = ss_slip  # SS Strike-Slip
        dsrc[8] = ds_slip  # DS Dip-Slip
        dsrc[9] = self.opening  # TS Tensional-Slip
        return dsrc

    def outline(self):
        coords = num.empty((4, 2))

        c_strike = num.cos(self.strike * d2r)
        s_strike = num.sin(self.strike * d2r)
        c_dip = num.cos(self.dip * d2r)

        coords[0, 0] = s_strike * self.length/2
        coords[0, 1] = c_strike * self.length/2
        coords[1, 0] = -coords[0, 0]
        coords[1, 1] = -coords[0, 1]

        coords[2, 0] = coords[1, 0] - c_strike * c_dip * self.width
        coords[2, 1] = coords[1, 1] + s_strike * c_dip * self.width
        coords[3, 0] = coords[0, 0] - c_strike * c_dip * self.width
        coords[3, 1] = coords[0, 1] + s_strike * c_dip * self.width

        coords[:, 0] += self.easting
        coords[:, 1] += self.northing
        return coords

    @property
    def segments(self):
        yield self


class OkadaSegment(OkadaSource):
    enabled = Bool.T(
        default=True,
        optional=True)


class OkadaPath(Object):

    __implements__ = 'disloc'

    origin_easting = Float.T(
        help='Easting of the origin in [m]')
    origin_northing = Float.T(
        help='Northing of the origin in [m]')
    nu = Float.T(
        default=1.25,
        help='Material parameter Nu in P s^-1')
    nodes = List.T(
        default=[],
        optional=True,
        help='Nodes of the segments as (easting, northing) tuple of [m]')
    segments__ = List.T(
        default=[],
        optional=True,
        help='List of all segments.')

    def __init__(self, *args, **kwargs):
        Object.__init__(self, *args, **kwargs)
        self._segments = []

        if not self.nodes:
            self.nodes.append(
                [self.origin_easting, self.origin_northing])

    @property
    def segments(self):
        return self._segments

    @segments.setter
    def segments(self, segments):
        self._segments = segments

    @staticmethod
    def _newSegment(e1, n1, e2, n2, **kwargs):
        dE = e2 - e1
        dN = n2 - n1
        length = (dN**2 + dE**2)**.5
        '''Width Scaling relation after

        Leonard, M. (2010). Earthquake fault scaling: Relating rupture length,
            width, average displacement, and moment release, Bull. Seismol.
            Soc. Am. 100, no. 5, 1971–1988.
        '''
        segment = {
            'northing': n1 + dN/2,
            'easting': e1 + dE/2,
            'depth': 0.,
            'length': length,
            'width': 15. * length**.66,
            'strike': num.arccos(dN/length) * r2d,
            'slip': 45.,
            'rake': 90.,
        }
        segment.update(kwargs)
        return OkadaSegment(**segment)

    def _moveSegment(self, pos, e1, n1, e2, n2):
        dE = e2 - e1
        dN = n2 - n1
        length = (dN**2 + dE**2)**.5

        segment_update = {
            'northing': n1 + dN/2,
            'easting': e1 + dE/2,
            'length': length,
            'width': 15. * length**.66,
            'strike': num.arccos(dN/length) * r2d,
        }

        segment = self.segments[pos]
        for attr, val in segment_update.iteritems():
            segment.__setattr__(attr, val)

    def addNode(self, easting, northing):
        self.nodes.append([easting, northing])
        print self.nodes
        self.segments.append(
            self._newSegment(
                e1=self.nodes[-2][0],
                n1=self.nodes[-2][1],
                e2=self.nodes[-1][0],
                n2=self.nodes[-1][1]))

    def insertNode(self, pos, easting, northing):
        self.nodes.insert(pos, [easting, northing])
        self.segments.append(
            self._newSegment(
                e1=self.nodes[pos][0],
                n1=self.nodes[pos][1],
                e2=self.nodes[pos+1][0],
                n2=self.nodes[pos+1][1]))
        self._moveSegment(
            pos-1,
            e1=self.nodes[pos-1][0],
            n1=self.nodes[pos-1][1],
            e2=self.nodes[pos][0],
            n2=self.nodes[pos][1],
            )

    def moveNode(self, pos, easting, northing):
        self.nodes[pos] = [easting, northing]
        if pos < len(self):
            self._moveSegment(
                pos,
                e1=self.nodes[pos][0],
                n1=self.nodes[pos][1],
                e2=self.nodes[pos+1][0],
                n2=self.nodes[pos+1][1])
        if pos != 0:
            self._moveSegment(
                pos,
                e1=self.nodes[pos-1][0],
                n1=self.nodes[pos-1][1],
                e2=self.nodes[pos][0],
                n2=self.nodes[pos][1])

    def __len__(self):
        return len(self.segments)

    def dislocSource(self):
        return num.array([seg.dislocSource() for seg in self.segments
                          if seg.enabled])


class DislocProcessor(object):
    __implements__ = 'disloc'

    @staticmethod
    def process(sources, coords, nthreads=0):
        result = {
            'processor_profile': dict()
        }

        src_arr = num.vstack([src.dislocSource() for src in sources])
        res = disloc_ext.disloc(src_arr, coords, src.nu, nthreads)

        result['north'] = res[:, 0]
        result['east'] = res[:, 1]
        result['down'] = res[:, 2]

        return result