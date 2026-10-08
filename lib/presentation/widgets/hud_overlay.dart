import 'package:flutter/material.dart';
import '../../data/models/kinematics.dart';

class GnssBadge extends StatelessWidget {
  final GnssStatus status;

  const GnssBadge({super.key, required this.status});

  @override
  Widget build(BuildContext context) {
    Color color;
    String text;
    bool isPulsing = false;

    switch (status) {
      case GnssStatus.strong:
        color = Colors.green;
        text = 'GNSS: Strong';
        break;
      case GnssStatus.degraded:
        color = Colors.orange;
        text = 'GNSS: Degraded';
        break;
      case GnssStatus.blackout:
        color = Colors.red;
        text = 'GNSS: Blackout - IDR Active';
        isPulsing = true;
        break;
    }

    Widget chip = Chip(
      backgroundColor: color.withValues(alpha: 0.9),
      labelStyle: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
      label: Text(text),
    );

    if (isPulsing) {
      // Very basic pulse effect could be done with AnimationController, 
      // but keeping it simple for the layout
      return TweenAnimationBuilder(
        tween: Tween<double>(begin: 0.5, end: 1.0),
        duration: const Duration(milliseconds: 500),
        builder: (context, value, child) {
          return Opacity(opacity: value, child: child);
        },
        child: chip,
        onEnd: () {
          // In a real implementation we'd loop this, but requires Stateful widget
        },
      );
    }

    return chip;
  }
}

class TelemetryHud extends StatelessWidget {
  final double speed;
  final double driftMeters;
  final bool isAligned;

  const TelemetryHud({
    super.key,
    required this.speed,
    required this.driftMeters,
    required this.isAligned,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.black87,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _buildMetric('Velocity', '${(speed * 3.6).toStringAsFixed(1)} km/h', Colors.cyan),
              _buildMetric('Drift', '${driftMeters.toStringAsFixed(2)} m', Colors.orange),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Icon(
                isAligned ? Icons.check_circle : Icons.warning,
                color: isAligned ? Colors.green : Colors.yellow,
                size: 20,
              ),
              const SizedBox(width: 8),
              Text(
                isAligned ? 'Alignment Matrix: OK' : 'Alignment Required',
                style: const TextStyle(color: Colors.white70),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildMetric(String label, String value, Color color) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(color: Colors.white54, fontSize: 12)),
        Text(value, style: TextStyle(color: color, fontSize: 24, fontWeight: FontWeight.bold)),
      ],
    );
  }
}
