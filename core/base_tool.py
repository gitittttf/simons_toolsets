from abc import ABC, abstractmethod
import tkinter as tk
from typing import Optional

class BaseTool(ABC):
    """
    Abstrakte Basisklasse für alle Tools in Simon's Toolset.
    Jedes neue Tool muss von dieser Klasse erben.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Der Name des Tools"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Eine kurze Beschreibung was das Tool macht"""
        pass
        
    @property
    def version(self) -> str:
        """Die Version des Tools"""
        return "1.0.0"
        
    @property
    def author(self) -> str:
        """Der Autor des Tools"""
        return "Simon"
    
    @abstractmethod
    def run(self):
        """
        Startet das Tool. 
        Dies ist der Einstiegspunkt wenn das Tool ausgewählt wird.
        """
        pass
