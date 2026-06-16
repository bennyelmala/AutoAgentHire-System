import { motion } from "framer-motion";
import { Check, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";

interface PricingCardProps {
  name: string;
  price: string;
  period: string;
  description: string;
  features: string[];
  buttonText: string;
  buttonVariant: "hero" | "outline" | "default";
  isPopular?: boolean;
  delay?: number;
}

const PricingCard = ({
  name,
  price,
  period,
  description,
  features,
  buttonText,
  buttonVariant,
  isPopular,
  delay = 0,
}: PricingCardProps) => (
  <motion.div
    initial={{ opacity: 0, y: 40 }}
    whileInView={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.6, delay }}
    viewport={{ once: true }}
    className={`relative p-8 rounded-2xl backdrop-blur-xl border transition-all duration-300 hover:-translate-y-2 ${
      isPopular
        ? "bg-gradient-to-b from-primary/20 to-card/80 border-primary/40 shadow-xl shadow-primary/20"
        : "bg-card/60 border-white/10 hover:border-primary/30"
    }`}
  >
    {isPopular && (
      <div className="absolute -top-4 left-1/2 -translate-x-1/2 px-4 py-1 bg-primary text-primary-foreground text-sm font-semibold rounded-full flex items-center gap-1">
        <Sparkles className="w-3 h-3" /> Most Popular
      </div>
    )}

    <div className="text-center mb-8">
      <h3 className="text-xl font-semibold mb-2 text-foreground">{name}</h3>
      <p className="text-muted-foreground text-sm mb-4">{description}</p>
      <div className="flex items-baseline justify-center gap-1">
        <span className="text-5xl font-bold font-display gradient-text">{price}</span>
        <span className="text-muted-foreground">{period}</span>
      </div>
    </div>

    <ul className="space-y-4 mb-8">
      {features.map((feature) => (
        <li key={feature} className="flex items-start gap-3">
          <div className="w-5 h-5 rounded-full bg-success/20 flex items-center justify-center flex-shrink-0 mt-0.5">
            <Check className="w-3 h-3 text-success" />
          </div>
          <span className="text-foreground/80 text-sm">{feature}</span>
        </li>
      ))}
    </ul>

    <Button variant={buttonVariant} size="lg" className="w-full" asChild>
      <Link to="/signup">{buttonText}</Link>
    </Button>
  </motion.div>
);

const plans = [
  {
    name: "Free",
    price: "$0",
    period: "/month",
    description: "Perfect for getting started",
    features: [
      "5 applications per day",
      "Basic job matching",
      "Resume upload",
      "Email support",
    ],
    buttonText: "Start Free",
    buttonVariant: "outline" as const,
  },
  {
    name: "Pro",
    price: "$29",
    period: "/month",
    description: "Best for active job seekers",
    features: [
      "25 applications per day",
      "AI-powered matching",
      "Custom cover letters",
      "Priority support",
      "Advanced analytics",
      "Resume optimization",
    ],
    buttonText: "Start Pro Trial",
    buttonVariant: "hero" as const,
    isPopular: true,
  },
  {
    name: "Enterprise",
    price: "$99",
    period: "/month",
    description: "For power users",
    features: [
      "Unlimited applications",
      "Dedicated account manager",
      "Custom integrations",
      "API access",
      "White-label options",
      "SLA guarantee",
    ],
    buttonText: "Contact Sales",
    buttonVariant: "outline" as const,
  },
];

export const PricingSection = () => {
  return (
    <section className="py-24 px-4 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-primary/5 to-transparent" />
      
      <div className="max-w-6xl mx-auto relative z-10">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          viewport={{ once: true }}
          className="text-center mb-16"
        >
          <h2 className="text-4xl md:text-5xl font-bold mb-6">
            Choose Your <span className="gradient-text">Plan</span>
          </h2>
          <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
            Start free and upgrade as you grow. All plans include a 14-day money-back guarantee.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {plans.map((plan, index) => (
            <PricingCard key={plan.name} {...plan} delay={index * 0.15} />
          ))}
        </div>
      </div>
    </section>
  );
};
