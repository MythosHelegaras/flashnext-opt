// Minimal stand-ins for the Godot API surface the published files touch, plus the
// EventBus contract exactly as HealthEvents.cs describes it. No game logic here.
namespace Godot {
  public class ExportAttribute : System.Attribute {}
  public class Node { public string Name {get;set;} = "Entity"; public Node? Parent; public virtual void _Ready(){} public Node? GetParent()=>Parent; }
  public static class GD { public static void PushWarning(string s)=>System.Console.WriteLine("warn: "+s); }
  public static class Mathf { public static int Max(int a,int b)=>System.Math.Max(a,b); public static int Min(int a,int b)=>System.Math.Min(a,b); }
}
namespace ReferenceProject.Systems.Health {
  // Stand-in for the unpublished DamageContext type. HealthComponent only reads Amount.
  public readonly record struct DamageContext(int Amount, Godot.Node? Source);
}
namespace ReferenceProject.Autoloads {
  using Godot; using ReferenceProject.Systems.Health;
  public partial class EventBus : Node {
    public static EventBus Instance {get;} = new EventBus();
    public event DamageTakenEventHandler? DamageTaken;
    public event HealingReceivedEventHandler? HealingReceived;
    public event HealthDepletedEventHandler? HealthDepleted;
    public void EmitDamageTaken(Node r, DamageContext c, int a, int cur, int max)=>DamageTaken?.Invoke(r,c,a,cur,max);
    public void EmitHealingReceived(Node r, int q, int a, int cur, int max)=>HealingReceived?.Invoke(r,q,a,cur,max);
    public void EmitHealthDepleted(Node r, DamageContext k)=>HealthDepleted?.Invoke(r,k);
  }
}
