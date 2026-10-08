import 'dart:convert';
import 'dart:math';
import 'package:flutter/services.dart';
import 'package:latlong2/latlong.dart';

class MapMatcher {
  final List<List<LatLng>> _roadSegments = [];
  bool _isLoaded = false;

  Future<void> loadMap(String assetPath) async {
    try {
      final String geoJsonString = await rootBundle.loadString(assetPath);
      final data = json.decode(geoJsonString);

      if (data['features'] != null) {
        for (var feature in data['features']) {
          if (feature['geometry']['type'] == 'LineString') {
            List coords = feature['geometry']['coordinates'];
            List<LatLng> segment = coords.map((c) => LatLng(c[1], c[0])).toList();
            _roadSegments.add(segment);
          }
        }
      }
      _isLoaded = true;
      print("Offline map matching loaded ${_roadSegments.length} segments.");
    } catch (e) {
      print("Failed to load map network: $e");
    }
  }

  /// Map matching execution: Snaps LatLng to nearest road if bearing aligns.
  LatLng snapToMap(LatLng currentPos, double currentBearing) {
    if (!_isLoaded || _roadSegments.isEmpty) return currentPos;

    LatLng bestSnap = currentPos;
    double minDistance = double.infinity;

    for (var segment in _roadSegments) {
      for (int i = 0; i < segment.length - 1; i++) {
        LatLng p1 = segment[i];
        LatLng p2 = segment[i + 1];

        // 1. Check heading alignment (must be within 45 degrees)
        double segmentBearing = _calculateBearing(p1, p2);
        double bearingDiff = (currentBearing - segmentBearing).abs();
        if (bearingDiff > 180) bearingDiff = 360 - bearingDiff;

        // Allow reverse direction as well
        double revBearingDiff = (currentBearing - (segmentBearing + 180) % 360).abs();
        if (revBearingDiff > 180) revBearingDiff = 360 - revBearingDiff;

        if (bearingDiff > 45 && revBearingDiff > 45) continue; // Heading doesn't align

        // 2. Project point onto segment
        LatLng projected = _projectPointOnSegment(currentPos, p1, p2);
        
        final Distance d = const Distance();
        double dist = d.as(LengthUnit.Meter, currentPos, projected);

        if (dist < minDistance && dist < 50.0) { // Max snap distance 50m
          minDistance = dist;
          bestSnap = projected;
        }
      }
    }

    return bestSnap;
  }

  double _calculateBearing(LatLng p1, LatLng p2) {
    double dLon = (p2.longitude - p1.longitude) * pi / 180.0;
    double lat1 = p1.latitude * pi / 180.0;
    double lat2 = p2.latitude * pi / 180.0;

    double y = sin(dLon) * cos(lat2);
    double x = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dLon);

    double brng = atan2(y, x) * 180.0 / pi;
    return (brng + 360) % 360;
  }

  LatLng _projectPointOnSegment(LatLng p, LatLng a, LatLng b) {
    // Simplified planar projection for small distances
    double aLat = a.latitude, aLon = a.longitude;
    double bLat = b.latitude, bLon = b.longitude;
    double pLat = p.latitude, pLon = p.longitude;

    double l2 = pow(aLat - bLat, 2).toDouble() + pow(aLon - bLon, 2).toDouble();
    if (l2 == 0) return a; // a == b case

    double t = ((pLat - aLat) * (bLat - aLat) + (pLon - aLon) * (bLon - aLon)) / l2;
    t = max(0, min(1, t)); // clamp to segment

    return LatLng(aLat + t * (bLat - aLat), aLon + t * (bLon - aLon));
  }
}
