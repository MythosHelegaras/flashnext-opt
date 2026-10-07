using System; using ReferenceProject.Autoloads; using ReferenceProject.Systems.Health;
public static class Probe { public static void Main() {
  var bus = EventBus.Instance; int depleted = 0; bool hit = false; HealthComponent? hc = null;
  bus.HealthDepleted += (r, k) => depleted++;
  // Case 1: one lethal hit, no re-entry
  hc = new HealthComponent { MaxHealth = 10 }; hc._Ready();
  hc.ApplyDamage(new DamageContext(10, null));
  Console.WriteLine($"no re-entry:      HealthDepleted fired {depleted}x");
  // Case 2: a DamageTaken subscriber applies one more hit synchronously (thorns, retaliation)
  depleted = 0; hc = new HealthComponent { MaxHealth = 10 }; hc._Ready();
  bus.DamageTaken += (r, c, a, cur, max) => { if (!hit) { hit = true; hc!.ApplyDamage(new DamageContext(5, null)); } };
  hc.ApplyDamage(new DamageContext(10, null));
  Console.WriteLine($"re-entrant hit:   HealthDepleted fired {depleted}x  (IsDepleted={hc.IsDepleted})");
}}
