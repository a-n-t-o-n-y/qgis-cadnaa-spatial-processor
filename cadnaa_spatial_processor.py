import os
from qgis.analysis import QgsZonalStatistics
from qgis.PyQt.QtCore import QVariant
from PyQt5.QtCore import QVariant
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (QgsProcessingAlgorithm,
                       QgsProcessingParameterFile,
                       QgsProcessingParameterFolderDestination,
                       QgsProcessingParameterNumber,
                       QgsRasterLayer,
                       QgsProcessingFeedback,
                       QgsVectorLayer,
                       QgsVectorFileWriter,
                       QgsField,
                       QgsExpression,
                       QgsExpressionContext,
                       QgsExpressionContextUtils,
                       edit,
                       QgsProject
                       )
import processing

class CadnaaProcessingAlgorithm(QgsProcessingAlgorithm):
    """
    This is an algorithm that takes dtm, dsm and vector layers and creates cadnaa spatial inputs.
    """

    def tr(self, string):
        """
        Returns a translatable string with the self.tr() function.
        """
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        # Must return a new copy of your algorithm.
        return CadnaaProcessingAlgorithm()

    def name(self):
        """
        Returns the unique algorithm name.
        """
        return 'CadnaA spatial processor'

    def displayName(self):
        """
        Returns the translated algorithm name.
        """
        return self.tr('Create CadnaA inputs')

    def group(self):
        """
        Returns the name of the group this algorithm belongs to.
        """
        return self.tr('Custom scripts')

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs
        to.
        """
        return 'customscripts'

    def shortHelpString(self):
        """
        Returns a localised short help string for the algorithm.
        """
        return self.tr('Takes in LIDAR DSM and DTM data plus 2D vector buildings, roads and rail from VectorMap geodatabase, creates inputs ready for CadnaA')

    def initAlgorithm(self, config=None):
        """
        Input and output parameters for the algorithm, user inputs.
        """
        # DTM tif file
        self.addParameter(
            QgsProcessingParameterFile(
                'DTM',
                self.tr('Input DTM raster layer'),
                extension="tif"
            )
        )
        # DSM tif file
        self.addParameter(
            QgsProcessingParameterFile(
                'DSM',
                self.tr('Input DSM raster layer'),
                extension="tif"
            )
        )
        # Geodatabase .gdb file
        self.addParameter(
            QgsProcessingParameterFile(
                'GDB',
                self.tr('Input VectorMap Geodatabase File'),
                extension="gdb",
                behavior=1
            )
        )
        # Size of contours 1m, 2m etc.
        self.addParameter(
            QgsProcessingParameterNumber(
                'INTERVAL',
                self.tr('Enter Contour Interval'),
                type=QgsProcessingParameterNumber.Integer,
                minValue=0.5
            )
        )     
        # Output folder
        self.addParameter(
            QgsProcessingParameterFolderDestination(
                'OUTPUT',
                self.tr('Output folder')
            )
        )

    def contour_raster_to_shp(self):
        """
        Generate contour lines from DTM and save as shapefile.
        """
        contour_raster = QgsRasterLayer(self.dtm_path, "DTM")
        output_contours_path = os.path.join(self.output_path, 'contours.shp')

        if not contour_raster.isValid():
            raise ValueError("Error loading raster layers")

        parameters = {
            'INPUT': contour_raster,
            'BAND': 1,
            'INTERVAL': self.interval,
            'FIELD_NAME': 'ELEV',
            'CREATE_3D': True,  # Set to True if you want 3D contours
            'IGNORE_NODATA': False,
            'OUTPUT': output_contours_path
        }

        feedback = QgsProcessingFeedback()

        processing.run("gdal:contour", parameters, feedback=feedback)
        contours = QgsVectorLayer(output_contours_path, "contours", "ogr")
        QgsProject.instance().addMapLayer(contours)

    def generate_height_difference_raster(self):
        """
        Generate a height difference raster from DSM minus DTM.
        """
        dtm_raster = QgsRasterLayer(self.dtm_path, "DTM")
        dsm_raster = QgsRasterLayer(self.dsm_path, "DSM")

        if not dtm_raster.isValid() or not dsm_raster.isValid():
            return print("Error loading raster layers.")
        else:
            height_raster_path = os.path.join(self.output_path, 'heights.tif')

            parameters = {
                'INPUT_A': dsm_raster,
                'BAND_A': 1,
                'INPUT_B': dtm_raster,
                'BAND_B': 1,
                'FORMULA': 'A-B',
                'OUTPUT': height_raster_path
            }
            processing.run('gdal:rastercalculator', parameters)

            return QgsRasterLayer(height_raster_path, "heights")

    def select_layer_in_gdb(self, layer_name):
        """
        Select a layer in the Geodatabase by name and return it as a QgsVectorLayer.
        """
        return QgsVectorLayer(f"{self.gdb_path}|layername={layer_name}", layer_name, "ogr")

    def select_feature_in_layer(self, vector_layer, column_name, feature_name):
        """
        Select a feature in a vector layer using a column name and feature name.
        """
        filter_expression = f"{column_name} = '{feature_name}'"
        vector_layer.setSubsetString(filter_expression)
        return vector_layer

    def export_selected_as_shp(self, vector_layer, output_name):
        """
        Export the selected vector layer as a shapefile with the specified output name.
        """
        output_file_path = os.path.join(self.output_path, output_name)
        QgsVectorFileWriter.writeAsVectorFormat(vector_layer, output_file_path, "UTF-8", vector_layer.crs(), "ESRI Shapefile")
        return output_file_path

    def assign_building_heights_to_shp(self, buildings_path, height_raster):
        """
        Assign height values to a buildings shapefile based on a height raster.
        """
        # load buildings shapefile
        buildings = QgsVectorLayer(buildings_path, "buildings", "ogr")

        # run zonal stats and assign mean, max and min values
        zonal_stats = QgsZonalStatistics(buildings, height_raster, "", 1, (QgsZonalStatistics.Min|QgsZonalStatistics.Max|QgsZonalStatistics.Mean))
        zonal_stats.calculateStatistics(None)

        # create new columns for cadnaa
        height_field = QgsField("HA", QVariant.Double)
        height_att = QgsField("HA_ATT", QVariant.String)
        buildings.dataProvider().addAttributes([height_field])
        buildings.dataProvider().addAttributes([height_att])
        buildings.updateFields()

        # assign mean value to HA column
        expression = QgsExpression("mean")

        # Create an expression context
        context = QgsExpressionContext()
        context.appendScope(QgsExpressionContextUtils.globalScope())

        # Set the expression context
        with edit(buildings):
            for feature in buildings.getFeatures():
                context.setFeature(feature)
                value = expression.evaluate(context)
                if expression.hasEvalError():
                    print(f"Error evaluating expression for feature {feature.id()}: {expression.evalErrorString()}")
                    continue
                feature["HA"] = value
                feature["HA_ATT"] = "r"
                buildings.updateFeature(feature)

        buildings.commitChanges()
        QgsProject.instance().addMapLayer(buildings)

    def generate_buildings(self, building_layer, building_column, building_feature):
        """
        Generate building features and assign heights to a shapefile.
        """
        height_raster = self.generate_height_difference_raster()
        selected_buildings = self.select_feature_in_layer(self.select_layer_in_gdb(building_layer), building_column,
                                                          building_feature)
        buildings_path = self.export_selected_as_shp(selected_buildings, "buildings.shp")
        self.assign_building_heights_to_shp(buildings_path, height_raster)

    def add_field_to_vector(self, vector_layer, field_name, new_value, data_type):

        # add field
        vector_layer.dataProvider().addAttributes([QgsField(field_name, data_type)])
        vector_layer.updateFields()
        print(vector_layer.fields().names())

        # edit field

        with edit(vector_layer):
            for feature in vector_layer.getFeatures():
                feature[field_name] = new_value
                vector_layer.updateFeature(feature)

        vector_layer.commitChanges()


    def export_layer_for_cadnaa(self, layer_name, output_name, field_name, new_value, data_type):
        selected_layer = self.select_layer_in_gdb(layer_name)
        exported_layer_path = self.export_selected_as_shp(selected_layer, f'{output_name}.shp')
        new_vector_layer = QgsVectorLayer(exported_layer_path, output_name, "ogr")
        QgsProject.instance().addMapLayer(new_vector_layer)
        self.add_field_to_vector(new_vector_layer, field_name, new_value, data_type)
        QgsProject.instance().addMapLayer(new_vector_layer)

    def process_data(self):
        """
        Process the data by executing various subtasks.
        """
        self.contour_raster_to_shp()
        self.generate_buildings("Area", "featureDescription", "Building Polygon")
        self.export_layer_for_cadnaa("RailCLine", "rail", "HA_ATT", "r", QVariant.String)
        self.export_layer_for_cadnaa("RoadCLine", "roads", "HA_ATT", "r", QVariant.String)

    def processAlgorithm(self, parameters, context, feedback):
        """
        Main entry point for the processing algorithm.
        """
        self.output_path = self.parameterAsString(parameters, 'OUTPUT', context)
        self.gdb_path = self.parameterAsString(parameters, 'GDB', context)
        self.dtm_path = self.parameterAsString(parameters, 'DTM', context)
        self.dsm_path = self.parameterAsString(parameters, 'DSM', context)
        self.interval =self.parameterAsInt(parameters, 'INTERVAL', context)
        self.process_data()
        return {}