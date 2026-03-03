"""
Binary frame format for ilx_pipeline - Python Implementation

This module implements the binary protocol used by the Innospace Pipeline service
for data transmission between clients and servers.
"""

import struct
import time
import logging
from datetime import datetime
from enum import IntEnum
import threading

# For Python 3.5 compatibility, define Any as object
try:
    from typing import Any, Callable, Dict, List, Optional
    # If typing is available, use it
except ImportError:
    # If typing is not available, define fallbacks
    class _Any:
        def __getitem__(self, item):
            return object
    Any = object
    Callable = object
    Dict = dict
    List = list
    Optional = object

# Set up logger for the module
logger = logging.getLogger(__name__)


class DataTypeCode(IntEnum):
    """Data type codes for payload type hinting in binary frames."""
    STRING = 0x01  # UTF-8 encoded string
    INT = 0x02     # 32-bit signed integer
    LONG = 0x03    # 64-bit signed integer
    FLOAT = 0x04   # 32-bit floating point
    DOUBLE = 0x05  # 64-bit floating point
    BOOL = 0x06    # Boolean value
    ACTION = 0x07  # Action type (global action identifier)


class CommandCode(IntEnum):
    """Command codes for binary protocol frames."""
    CONNECT_SERVICE = 0x0001 # Connect to a service
    SEND_TO_SERVICE = 0x0002  # Send data to a service
    SEND_TO_INPUT = 0x0003    # Send data to an input
    GET_INPUT_DATA = 0x0004   # Request input data
    DATA_UPDATE = 0x0007      # Data update notification
    RESPONSE = 0x0008         # Response to a command
    REFRESH_DATA = 0x0009     # Request to refresh data
    DELETE_DATAPOINT = 0x000A # Delete a datapoint
    UPDATE_DATAPOINT = 0x000B # Update a datapoint
    SERVICE_STATUS = 0x000C   # Service added/removed notification
    PUBLISH_ACTION = 0x000D       # Publish a supported action to the central service
    TRIGGER_ACTION = 0x000E       # Trigger a global action
    PUBLISH_CONFIG = 0x000F       # Publish a configuration entry to the central service
    CONFIG_UPDATE = 0x0010        # Config update broadcast from server to all clients
    PUBLISH_NOTIFICATION = 0x0011 # Publish/broadcast a notification to all connected services


# Constants for the binary protocol
START_OF_FRAME = 0xAA
API_VERSION = 0x02
END_OF_FRAME = 0x55


class TypedPayload:
    """
    Structure representing a payload with type information.
    
    Each payload in a frame consists of a type code (DataTypeCode) and raw binary data.
    The type code indicates how to interpret the bytes in the data field.
    
    :ivar type: Data type code indicating payload format
    :vartype type: DataTypeCode
    :ivar data: Raw binary payload data
    :vartype data: bytes
    """
    
    def __init__(self, data_type: DataTypeCode = DataTypeCode.STRING, data: Optional[bytes] = None):
        """
        Initialize a TypedPayload instance.
        
        :param data_type: Type code of the payload (default: STRING)
        :type data_type: DataTypeCode
        :param data: Raw payload data as bytes (default: empty bytes)
        :type data: Optional[bytes]
        """
        self.type = data_type
        self.data = data or b""
    
    @classmethod
    def from_string(cls, data_type: DataTypeCode, string_data: str):
        """
        Create a TypedPayload from string data.
        
        :param data_type: Type code for the payload
        :type data_type: DataTypeCode
        :param string_data: String to encode as UTF-8
        :type string_data: str
        :return: New TypedPayload instance
        :rtype: TypedPayload
        """
        return cls(data_type, string_data.encode('utf-8'))
    
    def to_string(self) -> str:
        """
        Convert payload data to string.
        
        :return: UTF-8 decoded string
        :rtype: str
        :raises UnicodeDecodeError: If data is not valid UTF-8
        """
        return self.data.decode('utf-8')


class BinaryFrame:
    """
    Structure representing a binary protocol frame.
    
    Frame format (all multi-byte integers in big-endian except payload data):
    
    +-------------------+--------+------------------------------------------------+
    | Field             | Size   | Description                                    |
    +===================+========+================================================+
    | start_of_frame    | 1 byte | Frame start marker (0xAA)                      |
    +-------------------+--------+------------------------------------------------+
    | api_version       | 1 byte | Protocol version (0x02)                        |
    +-------------------+--------+------------------------------------------------+
    | frame_length      | 4 bytes| Total length excluding header/CRC (big-endian) |
    +-------------------+--------+------------------------------------------------+
    | command_code      | 2 bytes| Command identifier (big-endian)                |
    +-------------------+--------+------------------------------------------------+
    | command_payload_id| 4 bytes| Request/response correlation ID (big-endian)   |
    +-------------------+--------+------------------------------------------------+
    | payload_count     | 2 bytes| Number of payloads in frame (big-endian)       |
    +-------------------+--------+------------------------------------------------+
    | payloads          | Variable| Array of TypedPayload structures              |
    +-------------------+--------+------------------------------------------------+
    | crc16             | 2 bytes| CRC-16-CCITT checksum (big-endian)            |
    +-------------------+--------+------------------------------------------------+
    
    .. note::
       Frame header fields use big-endian (network byte order), but payload
       data uses native byte order to match C++ std::memcpy behavior.
    
    :ivar start_of_frame: Frame start marker (always 0xAA)
    :vartype start_of_frame: int
    :ivar api_version: Protocol version (always 0x02)
    :vartype api_version: int
    :ivar frame_length: Length of frame data excluding header and CRC
    :vartype frame_length: int
    :ivar command_code: Command type identifier
    :vartype command_code: CommandCode
    :ivar command_payload_id: Request/response correlation ID
    :vartype command_payload_id: int
    :ivar payload_count: Number of payloads in frame
    :vartype payload_count: int
    :ivar payloads: List of typed payload structures
    :vartype payloads: List[TypedPayload]
    :ivar crc16: CRC-16-CCITT checksum
    :vartype crc16: int
    """
    
    def __init__(self):
        """Initialize a BinaryFrame with default values."""
        self.start_of_frame = START_OF_FRAME
        self.api_version = API_VERSION
        self.frame_length = 0
        self.command_code = CommandCode.SEND_TO_SERVICE
        self.command_payload_id = 0
        self.payload_count = 0
        self.payloads = []  # List of TypedPayload objects
        self.crc16 = 0
        self.end_of_frame = END_OF_FRAME


class BinaryFrameHandler:
    """
    Utility class for handling binary protocol frames.
    
    Provides static methods for frame serialization, deserialization, and CRC
    checksum calculation. Uses CRC-16-CCITT algorithm with polynomial 0x1021.
    """
    
    # CRC16-CCIT lookup table for efficient checksum calculation
    # Lazily initialized on first use with thread-safe double-checked locking
    _crc16_table = []  # type: List[int]
    _initialized = False
    _init_lock = threading.Lock()
    
    @classmethod
    def _init_crc16_table(cls):
        """
        Initialize the CRC16 lookup table for efficient checksum calculation.
        
        Uses CRC-16-CCITT polynomial 0x1021 (x^16 + x^12 + x^5 + 1).
        Implements double-checked locking for thread-safe lazy initialization.
        Table contains 256 precomputed values for fast byte-wise CRC updates.
        
        .. note::
           This method is called automatically by calculate_crc16_ccit() on first use.
           Multiple concurrent calls are safe due to lock protection.
        """
        if not cls._initialized:
            with cls._init_lock:
                # Double-check pattern: verify flag again inside lock
                if not cls._initialized:
                    # Generate lookup table: for each possible byte value (0-255)
                    for i in range(256):
                        crc = i << 8  # Shift byte to high position
                        # Process each bit in the byte
                        for j in range(8):
                            if crc & 0x8000:  # Check MSB
                                # XOR with polynomial if MSB is set
                                crc = (crc << 1) ^ 0x1021
                            else:
                                crc <<= 1
                        cls._crc16_table.append(crc & 0xFFFF)  # Store 16-bit result
                    cls._initialized = True
    
    @staticmethod
    def calculate_crc16_ccit(data: bytes) -> int:
        """
        Calculate CRC-16-CCITT checksum for data.
        
        Uses table-driven algorithm for efficient computation. The CRC is
        calculated over all frame data excluding the start byte and the
        CRC field itself.
        
        :param data: Binary data to checksum
        :type data: bytes
        :return: 16-bit CRC value (0x0000 to 0xFFFF)
        :rtype: int
        
        .. note::
           Initial CRC value is 0xFFFF. Each byte updates CRC using lookup table:
           ``crc = ((crc << 8) ^ table[(crc >> 8) ^ byte]) & 0xFFFF``
        """
        BinaryFrameHandler._init_crc16_table()
        crc = 0xFFFF  # Initial CRC value
        # Process each byte: lookup table provides precomputed polynomial result
        for byte in data:
            table_index = (crc >> 8) ^ byte
            crc = ((crc << 8) ^ BinaryFrameHandler._crc16_table[table_index]) & 0xFFFF
        return crc
    
    @staticmethod
    def serialize_frame(frame: BinaryFrame) -> bytes:
        """
        Serialize a BinaryFrame to bytes for transmission.
        
        Converts frame structure to binary format according to protocol specification.
        Frame length is calculated dynamically based on payload sizes. CRC is computed
        over frame data (excluding start, version, length, and CRC itself).
        
        :param frame: Frame object to serialize
        :type frame: BinaryFrame
        :return: Complete serialized frame with header, payloads, CRC, and end marker
        :rtype: bytes
        
        .. note::
           Frame length calculation:
           
           - Base: 6 bytes (command_code=2 + command_payload_id=2 + payload_count=2)
           - Per payload: 5 + len(data) bytes (length=4 + type=1 + data)
           - CRC region: All data after length field up to CRC itself
        """
        # Build the frame data excluding CRC and end of frame
        frame_data = bytearray()
        
        # Add fixed header fields
        frame_data.append(frame.start_of_frame)  # 0xAA
        frame_data.append(frame.api_version)     # 0x02
        
        # Calculate frame length: everything after this field up to and including CRC,
        # but excluding the frame_len field itself and the end-of-frame marker.
        # Includes: command_code(2) + command_payload_id(2) + payload_count(2) + all payloads + CRC(2)
        frame_len = 6  # Base size for command_code, command_payload_id, payload_count
        for payload in frame.payloads:
            # Each payload: length(4) + type(1) + data(n)
            frame_len += 4 + 1 + len(payload.data)
        frame_len += 2  # Include CRC in frame length (matches C++ serialization)
        
        # Add frame length (4 bytes, big-endian)
        frame_data.extend(struct.pack('>I', frame_len))
        
        # Add command code (2 bytes, big-endian)
        frame_data.extend(struct.pack('>H', frame.command_code.value))
        
        # Add command payload ID (2 bytes, big-endian)
        frame_data.extend(struct.pack('>H', frame.command_payload_id))
        
        # Add payload count (2 bytes, big-endian)
        frame_data.extend(struct.pack('>H', len(frame.payloads)))
        
        # Add payloads with their lengths and type hints
        for payload in frame.payloads:
            # Add payload length (4 bytes, big-endian)
            frame_data.extend(struct.pack('>I', len(payload.data)))
            
            # Add type hint (1 byte)
            frame_data.append(payload.type.value)
            
            # Add payload data
            frame_data.extend(payload.data)
        
        # Calculate and add CRC (2 bytes, big-endian)
        # CRC region: all data AFTER length field (from command_code onwards)
        # Excludes: start_of_frame(1) + api_version(1) + frame_length(4) = 6 bytes
        crc_data = frame_data[6:]  # Skip first 6 bytes
        crc = BinaryFrameHandler.calculate_crc16_ccit(crc_data)
        frame_data.extend(struct.pack('>H', crc))
        
        # Add end of frame marker (0x55)
        frame_data.append(frame.end_of_frame)
        
        return bytes(frame_data)
    
    @staticmethod
    def deserialize_frame(data: bytes) -> tuple:
        """
        Deserialize bytes to a BinaryFrame.
        
        Parses binary data and reconstructs frame structure. Validates frame markers,
        checks CRC integrity, and extracts all payloads. Supports partial data - if
        insufficient bytes available, returns 0 bytes_consumed for retry with more data.
        
        :param data: Binary data containing one or more frames
        :type data: bytes
        :return: Tuple of (success, frame, bytes_consumed)
            
            - success (bool): True if frame parsed successfully
            - frame (BinaryFrame): Deserialized frame object (or empty on failure)
            - bytes_consumed (int): Number of bytes consumed from input (0 if need more data)
        :rtype: tuple
        
        .. note::
           Returns (False, BinaryFrame(), 0) if insufficient data for complete frame.
           Returns (False, BinaryFrame(), n) if frame invalid (CRC/format error) where
           n is the number of bytes to skip.
        """
        # Minimum frame size: start(1) + version(1) + length(4) + cmd(2) + id(2) + 
        #                     count(2) + crc(2) + end(1) = 15 bytes (but we check 12 initially)
        if len(data) < 12:
            return False, BinaryFrame(), 0
        
        pos = 0
        
        # Verify start of frame marker (0xAA)
        if data[pos] != START_OF_FRAME:
            return False, BinaryFrame(), 0
        pos += 1
        
        # Check API version
        if data[pos] != API_VERSION:
            return False, BinaryFrame(), 0
        pos += 1
        
        # Read frame length (4 bytes, big-endian)
        if pos + 4 > len(data):
            return False, BinaryFrame(), 0
        frame_length = struct.unpack('>I', data[pos:pos+4])[0]
        pos += 4
        
        # Check if we have enough data for the entire frame
        if pos + frame_length > len(data):
            return False, BinaryFrame(), 0
        
        # Create frame object
        frame = BinaryFrame()
        frame.start_of_frame = START_OF_FRAME
        frame.api_version = API_VERSION
        frame.frame_length = frame_length
        
        # Read command code (2 bytes, big-endian)
        if pos + 2 > len(data):
            return False, BinaryFrame(), 0
        frame.command_code = CommandCode(struct.unpack('>H', data[pos:pos+2])[0])
        pos += 2
        
        # Read command payload ID (2 bytes, big-endian)
        if pos + 2 > len(data):
            return False, BinaryFrame(), 0
        frame.command_payload_id = struct.unpack('>H', data[pos:pos+2])[0]
        pos += 2
        
        # Read payload count (2 bytes, big-endian)
        if pos + 2 > len(data):
            return False, BinaryFrame(), 0
        payload_count = struct.unpack('>H', data[pos:pos+2])[0]
        pos += 2
        frame.payload_count = payload_count
        
        # Read payloads
        for i in range(payload_count):
            # Read payload length (4 bytes, big-endian)
            if pos + 4 > len(data):
                return False, BinaryFrame(), 0
            payload_len = struct.unpack('>I', data[pos:pos+4])[0]
            pos += 4
            
            # Read type hint (1 byte)
            if pos >= len(data):
                return False, BinaryFrame(), 0
            data_type = DataTypeCode(data[pos])
            pos += 1
            
            # Check if we have enough data for the payload
            if pos + payload_len > len(data):
                return False, BinaryFrame(), 0
            
            # Read payload data
            payload_data = data[pos:pos+payload_len]
            frame.payloads.append(TypedPayload(data_type, payload_data))
            pos += payload_len
        
        # Read CRC (2 bytes, big-endian)
        if pos + 2 > len(data):
            return False, BinaryFrame(), 0
        frame.crc16 = struct.unpack('>H', data[pos:pos+2])[0]
        pos += 2
        
        # Verify CRC
        crc_data_start = 6  # Skip start(1) + version(1) + length(4)
        crc_data_end = pos - 2  # Exclude CRC itself
        if crc_data_end > len(data):
            return False, BinaryFrame(), 0
        crc_data = data[crc_data_start:crc_data_end]
        calculated_crc = BinaryFrameHandler.calculate_crc16_ccit(crc_data)
        if calculated_crc != frame.crc16:
            return False, BinaryFrame(), 0
        
        # Check end of frame
        if pos >= len(data) or data[pos] != END_OF_FRAME:
            return False, BinaryFrame(), 0
        frame.end_of_frame = data[pos]
        pos += 1
        
        return True, frame, pos
    
    @staticmethod
    def add_payload(frame: BinaryFrame, data_type: DataTypeCode, payload: bytes):
        """Add a payload to the frame."""
        frame.payloads.append(TypedPayload(data_type, payload))
        frame.payload_count = len(frame.payloads)
    
    @staticmethod
    def add_string_payload(frame: BinaryFrame, data_type: DataTypeCode, string_payload: str):
        """Add a string payload to the frame."""
        payload_bytes = string_payload.encode('utf-8')
        frame.payloads.append(TypedPayload(data_type, payload_bytes))
        frame.payload_count = len(frame.payloads)
    
    @staticmethod
    def add_int_payload(frame: BinaryFrame, value: int):
        """Add an integer payload to the frame."""
        payload_bytes = struct.pack('=i', value)  # 4-byte signed integer, native byte order
        BinaryFrameHandler.add_payload(frame, DataTypeCode.INT, payload_bytes)
    
    @staticmethod
    def add_long_payload(frame: BinaryFrame, value: int):
        """Add a long integer payload to the frame."""
        payload_bytes = struct.pack('=q', value)  # 8-byte signed integer, native byte order
        BinaryFrameHandler.add_payload(frame, DataTypeCode.LONG, payload_bytes)
    
    @staticmethod
    def add_float_payload(frame: BinaryFrame, value: float):
        """Add a float payload to the frame."""
        payload_bytes = struct.pack('=f', value)  # 4-byte float, native byte order
        BinaryFrameHandler.add_payload(frame, DataTypeCode.FLOAT, payload_bytes)
    
    @staticmethod
    def add_double_payload(frame: BinaryFrame, value: float):
        """Add a double payload to the frame."""
        payload_bytes = struct.pack('=d', value)  # 8-byte double, native byte order
        BinaryFrameHandler.add_payload(frame, DataTypeCode.DOUBLE, payload_bytes)
    
    @staticmethod
    def add_bool_payload(frame: BinaryFrame, value: bool):
        """Add a boolean payload to the frame."""
        payload_bytes = struct.pack('=?', value)  # 1-byte boolean, native byte order
        BinaryFrameHandler.add_payload(frame, DataTypeCode.BOOL, payload_bytes)
    
    @staticmethod
    def add_timestamp_payload(frame: BinaryFrame, timestamp_us: int):
        """Add a timestamp payload to the frame."""
        payload_bytes = struct.pack('=q', timestamp_us)  # 8-byte signed integer for timestamp, native byte order
        BinaryFrameHandler.add_payload(frame, DataTypeCode.LONG, payload_bytes)
    
    @staticmethod
    def create_frame(cmd: CommandCode, cmd_id: int = 0) -> BinaryFrame:
        """Create a frame with a specific command and ID."""
        frame = BinaryFrame()
        frame.command_code = cmd
        frame.command_payload_id = cmd_id
        frame.payload_count = 0
        frame.payloads = []
        return frame
    
    @staticmethod
    def parse_frame_from_stream(stream_buffer: bytearray) -> tuple:
        """
        Parse frames from a stream buffer with boundary detection.
        
        Args:
            stream_buffer: Input buffer
            
        Returns:
            Tuple of (success: bool, parsed_frames: List[BinaryFrame])
        """
        parsed_frames = []
        pos = 0
        found_frame = False
        
        while pos < len(stream_buffer):
            # Look for start of frame
            start_pos = pos
            while start_pos < len(stream_buffer) and stream_buffer[start_pos] != START_OF_FRAME:
                start_pos += 1
            
            if start_pos >= len(stream_buffer):
                # No start of frame found, clear processed data
                del stream_buffer[:start_pos]
                break
            
            # Check if we have at least minimum frame size from start_pos
            if len(stream_buffer) - start_pos < 12:
                # Not enough data for a complete frame, keep remaining data
                del stream_buffer[:start_pos]
                break
            
            # Try to extract frame length from the potential frame
            length_pos = start_pos + 2  # Skip start and version
            if length_pos + 4 > len(stream_buffer):
                # Not enough data for frame length, keep remaining data
                del stream_buffer[:start_pos]
                break
            
            frame_len = struct.unpack('>I', stream_buffer[length_pos:length_pos+4])[0]
            
            # Total frame size = header + frame_len (which includes command_code, id, count, payloads, and CRC)
            total_frame_size = (length_pos - start_pos) + 4 + frame_len + 1  # +1 for end of frame
            
            if start_pos + total_frame_size > len(stream_buffer):
                # Not enough data for complete frame, keep remaining data
                del stream_buffer[:start_pos]
                break
            
            # Extract potential frame data
            frame_data = stream_buffer[start_pos:start_pos + total_frame_size]
            
            # Try to deserialize the frame
            success, frame, bytes_consumed = BinaryFrameHandler.deserialize_frame(frame_data)
            if success:
                parsed_frames.append(frame)
                found_frame = True
                # Move past the processed frame
                pos = start_pos + bytes_consumed
            else:
                # Invalid frame, move to next byte to look for a new start
                pos = start_pos + 1
        
        # Erase processed bytes from the buffer
        if pos > 0 and pos <= len(stream_buffer):
            del stream_buffer[:pos]
        
        return found_frame, parsed_frames


def get_iso8601_timestamp() -> str:
    """
    Get current timestamp in ISO 8601 format.
    
    Returns:
        Timestamp string in ISO 8601 format
    """
    now = datetime.utcnow()
    timestamp_str = now.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    return timestamp_str