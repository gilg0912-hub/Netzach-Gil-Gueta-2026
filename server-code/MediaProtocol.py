class MediaProtocol:
    # קבועים של סוגי הודעות
    TYPE_JOIN = 1
    TYPE_VIDEO = 2
    TYPE_LEAVE = 3
    TYPE_AUDIO = 4  # <--- הקבוע החדש שהוספנו עבור זרם השמע

    HEADER_SIZE = 73  # 1 (Type) + 36 (RoomID) + 36 (SenderID)

    @staticmethod
    def pack(pkt_type: int, room_id: str, sender_id: str, payload: bytes = b'') -> bytes:
        type_byte = pkt_type.to_bytes(1, 'big')

        room_bytes = room_id.encode('utf-8').ljust(36, b' ')[:36]
        sender_bytes = sender_id.encode('utf-8').ljust(36, b' ')[:36]

        return type_byte + room_bytes + sender_bytes + payload

    @staticmethod
    def unpack(data: bytes):
        if len(data) < MediaProtocol.HEADER_SIZE:
            return None, None, None, None

        pkt_type = int.from_bytes(data[:1], 'big')
        room_id = data[1:37].decode('utf-8').strip()
        sender_id = data[37:73].decode('utf-8').strip()
        payload = data[73:]

        return pkt_type, room_id, sender_id, payload