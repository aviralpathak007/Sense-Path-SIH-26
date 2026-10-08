import 'package:flutter/material.dart';

class CustomPuck extends StatelessWidget {
  final double bearing;
  final bool isBlackout;

  const CustomPuck({
    super.key,
    required this.bearing,
    this.isBlackout = false,
  });

  @override
  Widget build(BuildContext context) {
    return AnimatedRotation(
      turns: bearing / 360,
      duration: const Duration(milliseconds: 300),
      child: Container(
        width: 40,
        height: 40,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: isBlackout ? Colors.red.withValues(alpha: 0.3) : Colors.green.withValues(alpha: 0.3),
        ),
        child: Center(
          child: Container(
            width: 24,
            height: 24,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: Colors.white,
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.2),
                  blurRadius: 4,
                  spreadRadius: 1,
                )
              ],
            ),
            child: Icon(
              Icons.navigation,
              size: 16,
              color: isBlackout ? Colors.red : Colors.green,
            ),
          ),
        ),
      ),
    );
  }
}
