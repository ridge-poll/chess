class Profile {
  const Profile({
    required this.id,
    required this.name,
    required this.createdAt,
  });
  final int id;
  final String name;
  final DateTime createdAt;

  factory Profile.fromMap(Map<String, Object?> map) => Profile(
    id: map['id']! as int,
    name: map['name']! as String,
    createdAt: DateTime.parse(map['created_at']! as String),
  );
}
