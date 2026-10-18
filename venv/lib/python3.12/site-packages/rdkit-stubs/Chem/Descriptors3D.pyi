"""
 Descriptors derived from a molecule's 3D structure

"""
from __future__ import annotations
from rdkit.Chem.Descriptors import _isCallable
from rdkit.Chem import rdMolDescriptors
__all__: list[str] = ['CalcMolDescriptors3D', 'descList', 'rdMolDescriptors']
def CalcMolDescriptors3D(mol, confId = -1):
    """
    
        Compute all 3D descriptors of a molecule
        
        Arguments:
        - mol: the molecule to work with
        - confId: conformer ID to work with. If not specified the default (-1) is used
        
        Return:
        
        dict
            A dictionary with decriptor names as keys and the descriptor values as values
    
        raises a ValueError 
            If the molecule does not have conformers
        
    """
def _setupDescriptors(namespace):
    ...
descList: list  # value = [('PMI1', <function <lambda> at 0x105977060>), ('PMI2', <function <lambda> at 0x11543fc40>), ('PMI3', <function <lambda> at 0x11543fce0>), ('NPR1', <function <lambda> at 0x11543fd80>), ('NPR2', <function <lambda> at 0x11543fe20>), ('RadiusOfGyration', <function <lambda> at 0x11543fec0>), ('InertialShapeFactor', <function <lambda> at 0x11543ff60>), ('Eccentricity', <function <lambda> at 0x1154d4040>), ('Asphericity', <function <lambda> at 0x1154d40e0>), ('SpherocityIndex', <function <lambda> at 0x1154d4180>), ('PBF', <function <lambda> at 0x1154d4220>)]
