import 'dart:ui' as ui;
import 'dart:typed_data';
import 'package:flutter/services.dart';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';

class FallbackGridTileProvider extends TileProvider {
  @override
  ImageProvider getImage(TileCoordinates coordinates, TileLayer options) {
    return _FallbackGridImageProvider(coordinates);
  }
}

class _FallbackGridImageProvider extends ImageProvider<_FallbackGridImageProvider> {
  final TileCoordinates coordinates;

  _FallbackGridImageProvider(this.coordinates);

  @override
  Future<_FallbackGridImageProvider> obtainKey(ImageConfiguration configuration) {
    return Future.value(this);
  }

  @override
  ImageStreamCompleter loadImage(_FallbackGridImageProvider key, ImageDecoderCallback decode) {
    return MultiFrameImageStreamCompleter(
      codec: _loadAsync(key, decode),
      scale: 1.0,
      informationCollector: () => [DiagnosticsProperty('TileCoordinates', coordinates)],
    );
  }

  Future<ui.Codec> _loadAsync(_FallbackGridImageProvider key, ImageDecoderCallback decode) async {
    final String assetPath = 'assets/tiles/\${key.coordinates.z}/\${key.coordinates.x}/\${key.coordinates.y}.png';
    
    try {
      final ByteData data = await rootBundle.load(assetPath);
      final Uint8List bytes = data.buffer.asUint8List();
      final ui.ImmutableBuffer buffer = await ui.ImmutableBuffer.fromUint8List(bytes);
      return decode(buffer);
    } catch (_) {
      // Fallback: Generate a local grid overlay with coordinate ticks
      final Uint8List gridBytes = await _generateGridTile(key.coordinates);
      final ui.ImmutableBuffer buffer = await ui.ImmutableBuffer.fromUint8List(gridBytes);
      return decode(buffer);
    }
  }

  Future<Uint8List> _generateGridTile(TileCoordinates coords) async {
    final recorder = ui.PictureRecorder();
    final canvas = Canvas(recorder);
    final paint = Paint()
      ..color = const Color(0xFF222222)
      ..style = PaintingStyle.fill;
    
    // Background
    canvas.drawRect(const Rect.fromLTWH(0, 0, 256, 256), paint);
    
    // Grid Lines
    final linePaint = Paint()
      ..color = const Color(0xFF444444)
      ..strokeWidth = 1.0
      ..style = PaintingStyle.stroke;
      
    canvas.drawRect(const Rect.fromLTWH(0, 0, 256, 256), linePaint);
    
    // Text Label
    final textPainter = TextPainter(
      text: TextSpan(
        text: 'Z:\${coords.z} X:\${coords.x} Y:\${coords.y}\\nOFFLINE FALLBACK',
        style: const TextStyle(color: Colors.greenAccent, fontSize: 12),
      ),
      textDirection: TextDirection.ltr,
    );
    textPainter.layout();
    textPainter.paint(canvas, const Offset(10, 10));

    final picture = recorder.endRecording();
    final img = await picture.toImage(256, 256);
    final byteData = await img.toByteData(format: ui.ImageByteFormat.png);
    return byteData!.buffer.asUint8List();
  }
}
