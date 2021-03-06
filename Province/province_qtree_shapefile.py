import sys
import csv
from math import *
from quad_tree import *
from province_grid import *
from provinces import ProvinceSyncer
import shapefile
from matplotlib.path import Path
import numpy as np

def genSamplingPoints(startPoint, diff):
    return [startPoint
            # Inner round
            , startPoint + diff
            , Point(startPoint.x - diff.x, startPoint.y + diff.y)
            , startPoint - diff
            , Point(startPoint.x + diff.x, startPoint.y - diff.y)
            # Border corner
            , startPoint + diff*2
            , Point(startPoint.x - diff.x*2, startPoint.y + diff.y*2)
            , startPoint - diff*2
            , Point(startPoint.x + diff.x*2, startPoint.y - diff.y*2)
            # Border middle
            , Point(startPoint.x, startPoint.y + diff.y*2)
            , Point(startPoint.x, startPoint.y - diff.y*2)
            , Point(startPoint.x + diff.x*2, startPoint.y)
            , Point(startPoint.x - diff.x*2, startPoint.y)
            ]

class ProvinceShape:
    def __init__(self, name, pathPoints):
        self.name = name

        shapes = []
        shapes.append([])
        shapeCount = 0
        startPoint = pathPoints[0]
        shapes[shapeCount].append(startPoint)

        i = 1
        self.bbMin = Point(startPoint[0], startPoint[1])
        self.bbMax = Point(startPoint[0], startPoint[1])

        pointSum = Point(value = 0)

        while i < len(pathPoints):
            shapes[shapeCount].append(pathPoints[i])

            # Set bounding box
            x = pathPoints[i][0]
            y = pathPoints[i][1]
            if self.bbMin.x > x:
                self.bbMin.x = x
            if self.bbMin.y > y:
                self.bbMin.y = y
            if self.bbMax.x < x:
                self.bbMax.x = x
            if self.bbMax.y < y:
                self.bbMax.y = y

            pointSum.x += x
            pointSum.y += y

            # Split shapes
            if pathPoints[i] == startPoint:
                shapes.append([])
                shapeCount += 1
                i += 1
                try:
                    startPoint = pathPoints[i]
                    shapes[shapeCount].append(startPoint)
                except:
                    del shapes[shapeCount]
                    break
            i += 1

        # self.path = Path(np.array(pathPoints))
        self.paths = []
        for shape in shapes:
            self.paths.append(Path(np.array(shape)))

        self.centroid = pointSum / len(pathPoints)


    def isContainPoint(self, point):
        for path in self.paths:
            if path.contains_point(point):
                return True

        return False

    def isIntersectBBox(self, bbox):
        for path in self.paths:
            if path.intersects_bbox(bbox):
                return True

        return False

def buildGridAndTree(shapeFile, boxKm = 10):

    overAllBBox = Rectangle(
        btmLeft = Point(shapeFile.bbox[0], shapeFile.bbox[1])
        , topRight = Point(shapeFile.bbox[2], shapeFile.bbox[3])
    )
    midPoint = (overAllBBox.btmLeft + overAllBBox.topRight) / 2

    if overAllBBox.getWidth() > overAllBBox.getHeight():
        mainSideWidth = overAllBBox.getWidth()
    else:
        mainSideWidth = overAllBBox.getHeight()

    mainHalfWidth = Point(value = mainSideWidth/2)

    pvGrid = ProviGridParm(
        btmLeft = midPoint - mainHalfWidth
        , topRight = midPoint + mainHalfWidth
        , boxKm = boxKm
    )

    print 'Maxlevel: '+str(pvGrid.maxLevel)

    pvTree = QuadTree(
        level = 0
        , rect = Rectangle(
            btmLeft = pvGrid.btmLeft
            , topRight = pvGrid.topRight
        )
        , maxLevel = pvGrid.maxLevel
    )

    return (pvGrid, pvTree)

def buildProvinceShape(shapeFile, provinceAbbrCsv):
    pvPaths = shapeFile.shapes()
    records = shapeFile.records()
    pvShapes = {}
    pvSyncer = ProvinceSyncer(provinceAbbrCsv)
    for i in range(len(records)):
        name = pvSyncer.SyncProvinceName(records[i][2])
        if name not in pvShapes.keys():
            pvShapes[name] = ProvinceShape(
                    name = name
                    , pathPoints = pvPaths[i].points
                )
    return pvShapes

def scanGridByProvince(pvGrid, pvTree, pvShapes):
    for pvShape in pvShapes.values():
        print pvShape.name

        # Get border grid
        topLeft = pvGrid.snapToGrid(
            Point(pvShape.bbMin.x, pvShape.bbMax.y)
        )
        topRight = pvGrid.snapToGrid(pvShape.bbMax)
        btmLeft = pvGrid.snapToGrid(pvShape.bbMin)

        # Get number of grid in lat lon
        nLonBox = int((topRight.x - topLeft.x) / pvGrid.lonBoxSize)
        nLatBox = int((topLeft.y - btmLeft.y) / pvGrid.latBoxSize)

        for iLat in range(nLatBox) :
            for iLon in range(nLonBox):
                lat = topLeft.y - (iLat + 0.5) * pvGrid.latBoxSize
                lon = topLeft.x + (iLon + 0.5) * pvGrid.lonBoxSize
                testPoints = genSamplingPoints(Point(lon, lat), Point(pvGrid.lonBoxSize/4, pvGrid.latBoxSize/4))

                count = 0
                for point in testPoints:
                    if pvShape.isContainPoint(point.getTuple()):
                        count += 1

                if count != 0:
                    pvTree.AddDictValue(
                        point= Point(lon, lat)
                        , value ={count / float(len(testPoints))
                            : pvShape.name})

    pvTree.OptimizeTree()

if __name__ == '__main__':

    if(len(sys.argv) < 4):
        print 'Please insert province shapefile and export file names'
        exit()

    sf = shapefile.Reader(sys.argv[1])
    gridSize = input('Grid size(km): ')
    pvGrid, pvTree = buildGridAndTree(sf, boxKm = gridSize)
    pvTree.Span()
    pvShapes = buildProvinceShape(sf, './Province from Wiki Html table to CSV/ThailandProvinces_abbr.csv')

    scanGridByProvince(pvGrid, pvTree, pvShapes)

    # Write out
    pvTree.WriteBoxCSVStart(csvFileName = sys.argv[2])
    pvTree.exportTreeStructStart(csvFileName = sys.argv[3])
