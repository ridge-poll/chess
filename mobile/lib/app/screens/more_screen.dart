import 'package:flutter/material.dart';

import '../../domain/app_controller.dart';

class MoreScreen extends StatefulWidget {
  const MoreScreen({required this.controller, super.key});
  final AppController controller;

  @override
  State<MoreScreen> createState() => _MoreScreenState();
}

class _MoreScreenState extends State<MoreScreen> {
  late final TextEditingController _username;

  AppController get controller => widget.controller;

  @override
  void initState() {
    super.initState();
    _username = TextEditingController(
      text: controller.activeProfile?.chessComUsername ?? '',
    );
  }

  @override
  void dispose() {
    _username.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.fromLTRB(16, 18, 16, 32),
    children: [
      _sectionLabel(context, 'PROFILE'),
      const SizedBox(height: 8),
      Row(
        children: [
          Expanded(
            child: DropdownButtonFormField<int>(
              key: ValueKey(controller.activeProfile?.id),
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
              onChanged: (value) async {
                if (value == null) return;
                await controller.selectProfile(value);
                _username.text =
                    controller.activeProfile?.chessComUsername ?? '';
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
      _sectionLabel(context, 'CHESS.COM'),
      const SizedBox(height: 8),
      TextField(
        controller: _username,
        autocorrect: false,
        textCapitalization: TextCapitalization.none,
        decoration: const InputDecoration(
          border: OutlineInputBorder(),
          labelText: 'Username',
          prefixIcon: Icon(Icons.alternate_email),
        ),
      ),
      const SizedBox(height: 12),
      Row(
        children: [
          Expanded(
            child: DropdownButtonFormField<int>(
              key: ValueKey(
                '${controller.activeProfile?.id}-${controller.activeProfile?.syncDays}',
              ),
              initialValue: controller.activeProfile?.syncDays ?? 7,
              decoration: const InputDecoration(
                border: OutlineInputBorder(),
                labelText: 'Sync period',
              ),
              items: const [7, 14, 30, 90]
                  .map(
                    (days) => DropdownMenuItem(
                      value: days,
                      child: Text('$days days'),
                    ),
                  )
                  .toList(),
              onChanged: (value) {
                if (value != null) _save(days: value);
              },
            ),
          ),
          const SizedBox(width: 10),
          FilledButton.icon(
            onPressed: controller.syncState == SyncState.syncing
                ? null
                : _saveAndSync,
            icon: controller.syncState == SyncState.syncing
                ? const SizedBox.square(
                    dimension: 18,
                    child: CircularProgressIndicator.adaptive(strokeWidth: 2),
                  )
                : const Icon(Icons.refresh_rounded),
            label: const Text('Sync'),
          ),
        ],
      ),
      if (controller.syncMessage != null) ...[
        const SizedBox(height: 10),
        Text(
          controller.syncMessage!,
          style: TextStyle(
            fontSize: 13,
            color: controller.syncState == SyncState.failure
                ? Theme.of(context).colorScheme.error
                : Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
      ],
      const SizedBox(height: 28),
      _sectionLabel(context, 'APPEARANCE'),
      SwitchListTile.adaptive(
        contentPadding: EdgeInsets.zero,
        title: const Text('Dark mode'),
        value: controller.settings.darkMode,
        onChanged: (_) => controller.toggleTheme(),
      ),
      const SizedBox(height: 24),
      _sectionLabel(context, 'LOCAL-FIRST'),
      const SizedBox(height: 8),
      Text(
        'Profiles and imported games are stored on this device and remain available offline.',
        style: TextStyle(
          height: 1.45,
          color: Theme.of(context).colorScheme.onSurfaceVariant,
        ),
      ),
    ],
  );

  Widget _sectionLabel(BuildContext context, String label) => Text(
    label,
    style: Theme.of(context).textTheme.labelSmall?.copyWith(letterSpacing: 1.1),
  );

  Future<void> _save({int? days}) => controller.saveSyncPreferences(
    username: _username.text,
    days: days ?? controller.activeProfile?.syncDays ?? 7,
  );

  Future<void> _saveAndSync() async {
    await _save();
    await controller.syncGames();
  }

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
    if (name != null) {
      await controller.createProfile(name);
      _username.clear();
    }
  }
}
