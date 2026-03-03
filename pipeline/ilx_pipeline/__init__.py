"""
Innospace Pipeline Python Library

This library provides a Python interface to the Innospace Pipeline service,
allowing Python applications to connect to the pipeline server and exchange data
with other services.
"""

from .pipeline_client import (PipelineClient, DataType, EventType, EventStatus, EventData,
                               Config, NotificationType, NotificationPriority,
                               NotificationCategory, NotificationData)
from .pipeline_socket import PipelineSocket, SocketMode, SocketEvent, SocketEventData
from .binary_frame import BinaryFrame, BinaryFrameHandler, DataTypeCode, CommandCode, TypedPayload

__version__ = "1.0.0"
__author__ = "Innospace Automation Services Pvt. Ltd"
__all__ = [
    'PipelineClient',
    'DataType',
    'EventType',
    'EventStatus',
    'EventData',
    'Config',
    'NotificationType',
    'NotificationPriority',
    'NotificationCategory',
    'NotificationData',
    'PipelineSocket',
    'SocketMode',
    'SocketEvent',
    'SocketEventData',
    'BinaryFrame',
    'BinaryFrameHandler',
    'DataTypeCode',
    'CommandCode',
    'TypedPayload'
]