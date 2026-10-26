import 'package:flutter/material.dart';

import '../../domain/app_controller.dart';

class MoreScreen extends StatelessWidget {
  const MoreScreen({required this.controller, super.key});
  final AppController controller;

  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.fromLTRB(16, 18, 16, 32),
    children: [
      Text(
        'PROFILE',
        style: Theme.of(context).textTheme.labelSmall
            ?.copyWith(letterSpacing: 1.1),
      ),
      const SizedBox(height: 8),
      Row(
        children: [
          Expanded(
            child: DropdownButtonFormField<int>(
              initialValue: controller.activeProfile?.id,
              decoration: const InputDecoration(
                border: OutlineInputBorder(),
                labelText: 'Active profile',
              ),
              items: controller.availableProfiles
                  .map(
                    (profile) => DropdownMenuItem(
                      value: profile.id,
                      child: Text(profile.name),
                    ),
                  )
                  .toList(),
              onChanged: (value) {
                if (value != null) controller.selectProfile(value);
              },
            ),
          ),
          const SizedBox(width: 8),
          IconButton.filledTonal(
            onPressed: () => _createProfile(context),
            tooltip: 'Create profile',
            icon: const Icon(Icons.person_add_alt_1),
          ),
        ],
      ),
      const SizedBox(height: 28),
      Text(
        'APP',
        style: Theme.of(context).textTheme.labelSmall
            ?.copyWith(letterSpacing: 1.1),
      ),
      SwitchListTile.adaptive(
        contentPadding: EdgeInsets.zero,
        title: const Text('Dark mode'),
        value: controller.settings.darkMode,
        onChanged: (_) => controller.toggleTheme(),
      ),
      ListTile(
        contentPadding: EdgeInsets.zero,
        title: const Text('Sync window'),
        subtitle: const Text('Stored locally for this installation'),
        trailing: DropdownButton<int>(
          value: controller.settings.syncDays,
          items: const [7, 14, 30, 90]
              .map(
                (days) =>
                    DropdownMenuItem(value: days, child: Text('$days days')),
              )
              .toList(),
          onChanged: (value) {
            if (value != null) controller.setSyncDays(value);
          },
        ),
      ),
      const SizedBox(height: 28),
      Text(
        'LOCAL-FIRST',
        style: Theme.of(context).textTheme.labelSmall
            ?.copyWith(letterSpacing: 1.1),
      ),
      const SizedBox(height: 8),
      Text(
        'Profiles, games, settings, and future analysis are stored on this device. This app does not require FastAPI or your Mac to launch.',
        style: TextStyle(
          height: 1.45,
          color: Theme.of(context).colorScheme.onSurfaceVariant,
        ),
      ),
    ],
  );

  Future<void> _createProfile(BuildContext context) async {
    final text = TextEditingController();
    final name = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Create profile'),
        content: TextField(
          controller: text,
          autofocus: true,
          textCapitalization: TextCapitalization.words,
          decoration: const InputDecoration(labelText: 'Profile name'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, text.text),
            child: const Text('Create'),
          ),
        ],
      ),
    );
    text.dispose();
    if (name != null) await controller.createProfile(name);
  }
}
