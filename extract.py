#!/usr/bin/env python3
import sys
import os
import zlib
import struct

def main():
    if len(sys.argv) < 2:
        raise Exception("Usage: {} <akeeba-archive> [extract-path]".format(sys.argv[0]))
    
    archive_path = sys.argv[1]
    target = sys.argv[2] if len(sys.argv) > 2 else '.'

    # Open the archive in binary mode.
    with open(archive_path, 'rb') as archive:
        # The first three bytes should be the magic b'JPA'
        magic = archive.read(3)
        if magic != b'JPA':
            raise Exception("This does not seem to be an Akeeba Backup archive")

        # Read header information.
        header_size, = struct.unpack('<H', archive.read(2))
        vmaj, vmin = struct.unpack('<BB', archive.read(2))
        print("JPA Version: {}.{}".format(vmaj, vmin))

        entitycount, = struct.unpack('<L', archive.read(4))
        print("Entities: {}".format(entitycount))

        usize, csize = struct.unpack('<LL', archive.read(8))
        print("Uncompressed size: {} bytes, compressed: {} bytes".format(usize, csize))

        # Check for span marker.
        span_or_file = archive.read(3)
        if span_or_file == b'JP\x01':
            # Consume extra magic and fixed header size.
            archive.read(1 + 2)
            spans, = struct.unpack('<H', archive.read(2))
            print("Spans: {}".format(spans))
            if spans > 1:
                raise NotImplementedError("Span support is absent")
            span_or_file = archive.read(3)
        print()

        # Use the filesystem encoding for file names.
        fs_encoding = sys.getfilesystemencoding()

        # Process all entities.
        while span_or_file:
            if span_or_file != b'JPF':
                raise Exception("Invalid file header magic: {}".format(span_or_file))

            header_size, = struct.unpack('<H', archive.read(2))
            path_len, = struct.unpack('<H', archive.read(2))
            path_bytes = archive.read(path_len)
            try:
                # Decode the path using the filesystem encoding.
                path = path_bytes.decode(fs_encoding)
            except UnicodeDecodeError:
                path = path_bytes.decode(fs_encoding, errors='replace')

            type_index = struct.unpack('<B', archive.read(1))[0]
            entity_types = ['dir', 'file', 'link']
            try:
                entity_type = entity_types[type_index]
            except IndexError:
                raise Exception("Unknown entity type code: {}".format(type_index))

            comp_index = struct.unpack('<B', archive.read(1))[0]
            compressions = ['none', 'gzip', 'bzip2']
            try:
                compression = compressions[comp_index]
            except IndexError:
                raise Exception("Unknown compression type code: {}".format(comp_index))

            csize, usize, chmod = struct.unpack('<LLL', archive.read(12))

            print("{} [{}] (compression: {}) {} bytes {:o}".format(path, entity_type, compression, usize, chmod))

            # Check for extra header data.
            expected_header_size = 3 + 2 + 2 + path_len + 1 + 1 + 12
            if header_size > expected_header_size:
                extra, elen = struct.unpack('<HH', archive.read(4))
                if extra != 256:
                    print(extra)
                    raise Exception("Unknown extra field")
                archive.read(4)  # Consume timestamp

            if entity_type == 'file':
                out_path = os.path.join(target, path)
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                data = archive.read(csize)
                if compression == 'gzip':
                    file_data = zlib.decompress(data, -15)
                elif compression == 'none':
                    file_data = data
                else:
                    raise NotImplementedError("Unknown compression: " + compression)
                with open(out_path, 'wb') as outfile:
                    outfile.write(file_data)
            elif entity_type == 'dir':
                out_path = os.path.join(target, path)
                os.makedirs(out_path, exist_ok=True)
            else:
                raise NotImplementedError("Unknown entity type: " + entity_type)

            # Read the next 3-byte header magic (or empty if at EOF)
            span_or_file = archive.read(3)

if __name__ == '__main__':
    main()

